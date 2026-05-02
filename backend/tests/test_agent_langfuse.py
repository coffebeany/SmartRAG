"""Unit tests for the Agent Langfuse observability pipeline.

Verifies that:
1. _AgentLangfuseTracker correctly creates trace, generation, and tool spans
2. handle_event() maps astream_events v2 events to the right Langfuse calls
3. The tracker works gracefully when Langfuse is disabled (empty context)
4. finalize() calls end_rag_trace and returns trace_id
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — lightweight fakes for Langfuse objects
# ---------------------------------------------------------------------------

class FakeGeneration:
    """Mimics StatefulGenerationClient."""

    def __init__(self):
        self.ended = False
        self.end_kwargs: dict[str, Any] = {}

    def end(self, **kwargs: Any) -> "FakeGeneration":
        self.ended = True
        self.end_kwargs = kwargs
        return self


class FakeSpan:
    """Mimics StatefulSpanClient."""

    def __init__(self):
        self.ended = False
        self.end_kwargs: dict[str, Any] = {}

    def end(self, **kwargs: Any) -> "FakeSpan":
        self.ended = True
        self.end_kwargs = kwargs
        return self


class FakeTrace:
    """Mimics StatefulTraceClient."""

    def __init__(self, trace_id: str = "trace-abc-123"):
        self.id = trace_id
        self.generations: list[FakeGeneration] = []
        self.spans: list[FakeSpan] = []
        self._update_calls: list[dict] = []

    def generation(self, **kwargs: Any) -> FakeGeneration:
        gen = FakeGeneration()
        self.generations.append(gen)
        return gen

    def span(self, **kwargs: Any) -> FakeSpan:
        span = FakeSpan()
        self.spans.append(span)
        return span

    def update(self, **kwargs: Any) -> "FakeTrace":
        self._update_calls.append(kwargs)
        return self


class FakeTraceContext:
    """Mimics _RagTraceContext."""

    def __init__(self, trace: FakeTrace | None):
        self.trace = trace
        self.trace_id: str = trace.id if trace else ""


# ---------------------------------------------------------------------------
# Import the tracker class under test
# ---------------------------------------------------------------------------

from app.services.smartrag_agent import _AgentLangfuseTracker


class TestAgentLangfuseTrackerDisabled:
    """When Langfuse is disabled, tracker should be a no-op."""

    def test_disabled_with_none(self):
        tracker = _AgentLangfuseTracker(None)
        assert tracker.trace_id == ""
        # All methods should be no-ops
        tracker.on_chat_model_start("run1", "gpt-4")
        tracker.on_chat_model_stream("run1", "hello")
        tracker.on_chat_model_end("run1", "hello world")
        tracker.on_tool_start("run2", "search", {"q": "test"})
        tracker.on_tool_end("run2", "result")
        assert tracker.finalize(output={"status": "done"}, status="completed") == ""

    def test_disabled_with_empty_context(self):
        from app.observability.langfuse_integration import _EMPTY_CONTEXT

        tracker = _AgentLangfuseTracker(_EMPTY_CONTEXT)
        assert tracker.trace_id == ""
        tracker.on_chat_model_start("run1", "gpt-4")
        assert tracker.finalize(output={}, status="done") == ""


class TestAgentLangfuseTrackerEnabled:
    """When Langfuse is enabled, tracker should create spans and generations."""

    def _make_tracker(self) -> tuple[_AgentLangfuseTracker, FakeTrace]:
        trace = FakeTrace("trace-test-001")
        ctx = FakeTraceContext(trace)
        tracker = _AgentLangfuseTracker(ctx)
        return tracker, trace

    def test_trace_id_available(self):
        tracker, trace = self._make_tracker()
        assert tracker.trace_id == "trace-test-001"

    def test_llm_generation_lifecycle(self):
        tracker, trace = self._make_tracker()

        # Start LLM call
        tracker.on_chat_model_start("llm-run-1", "deepseek-r1", [{"role": "user", "content": "hi"}])
        assert len(trace.generations) == 1
        gen = trace.generations[0]
        assert not gen.ended

        # Stream tokens
        tracker.on_chat_model_stream("llm-run-1", "Hello")
        tracker.on_chat_model_stream("llm-run-1", " world")

        # End LLM call
        tracker.on_chat_model_end("llm-run-1")
        assert gen.ended
        assert gen.end_kwargs.get("output") == "Hello world"

    def test_llm_generation_with_explicit_output(self):
        tracker, trace = self._make_tracker()
        tracker.on_chat_model_start("llm-run-2", "gpt-4")
        tracker.on_chat_model_end("llm-run-2", "explicit output")
        gen = trace.generations[0]
        assert gen.ended
        assert gen.end_kwargs.get("output") == "explicit output"

    def test_tool_span_lifecycle(self):
        tracker, trace = self._make_tracker()

        tracker.on_tool_start("tool-run-1", "list_batches", {"limit": 10})
        assert len(trace.spans) == 1
        span = trace.spans[0]
        assert not span.ended

        tracker.on_tool_end("tool-run-1", {"batches": [{"id": "b1"}]})
        assert span.ended
        assert span.end_kwargs.get("output") == {"batches": [{"id": "b1"}]}

    def test_tool_span_error(self):
        tracker, trace = self._make_tracker()
        tracker.on_tool_start("tool-run-2", "delete_batch", {"id": "b1"})
        tracker.on_tool_error("tool-run-2", "not found")
        span = trace.spans[0]
        assert span.ended
        assert span.end_kwargs.get("level") == "ERROR"

    def test_multiple_concurrent_operations(self):
        """Multiple LLM calls and tool calls can be tracked simultaneously."""
        tracker, trace = self._make_tracker()

        # Start LLM
        tracker.on_chat_model_start("llm-1", "gpt-4")
        # Start tool (while LLM is streaming)
        tracker.on_tool_start("tool-1", "search", {"q": "test"})
        # Stream LLM
        tracker.on_chat_model_stream("llm-1", "thinking...")
        # End tool
        tracker.on_tool_end("tool-1", "search results")
        # End LLM
        tracker.on_chat_model_end("llm-1")

        assert len(trace.generations) == 1
        assert len(trace.spans) == 1
        assert trace.generations[0].ended
        assert trace.spans[0].ended


class TestHandleEvent:
    """Test handle_event() with realistic astream_events v2 payloads."""

    def _make_tracker(self) -> tuple[_AgentLangfuseTracker, FakeTrace]:
        trace = FakeTrace("trace-events-001")
        ctx = FakeTraceContext(trace)
        tracker = _AgentLangfuseTracker(ctx)
        return tracker, trace

    def test_chat_model_start_event(self):
        tracker, trace = self._make_tracker()
        tracker.handle_event(
            {
                "event": "on_chat_model_start",
                "run_id": "run-1",
                "name": "ChatOpenAI",
                "data": {"input": [{"role": "user", "content": "hello"}]},
            },
            model_name="deepseek-r1",
        )
        assert len(trace.generations) == 1

    def test_chat_model_stream_and_end(self):
        tracker, trace = self._make_tracker()
        # Start
        tracker.handle_event(
            {"event": "on_chat_model_start", "run_id": "r1", "name": "ChatOpenAI", "data": {}},
            model_name="gpt-4",
        )
        # Stream - create a mock chunk with content attribute
        mock_chunk = MagicMock()
        mock_chunk.content = "hello"
        mock_chunk.additional_kwargs = {}
        tracker.handle_event(
            {"event": "on_chat_model_stream", "run_id": "r1", "data": {"chunk": mock_chunk}},
            model_name="gpt-4",
        )
        # End
        tracker.handle_event(
            {"event": "on_chat_model_end", "run_id": "r1", "data": {"output": None}},
            model_name="gpt-4",
        )
        assert trace.generations[0].ended
        assert trace.generations[0].end_kwargs.get("output") == "hello"

    def test_tool_start_and_end_events(self):
        tracker, trace = self._make_tracker()
        tracker.handle_event(
            {
                "event": "on_tool_start",
                "run_id": "t1",
                "name": "list_batches",
                "data": {"input": {"limit": 5}},
            },
            model_name="gpt-4",
        )
        assert len(trace.spans) == 1

        tracker.handle_event(
            {
                "event": "on_tool_end",
                "run_id": "t1",
                "data": {"output": "result data"},
            },
            model_name="gpt-4",
        )
        assert trace.spans[0].ended

    def test_tool_error_event(self):
        tracker, trace = self._make_tracker()
        tracker.handle_event(
            {"event": "on_tool_start", "run_id": "t2", "name": "delete_run", "data": {"input": {}}},
            model_name="gpt-4",
        )
        tracker.handle_event(
            {"event": "on_tool_error", "run_id": "t2", "data": {"error": "timeout"}},
            model_name="gpt-4",
        )
        assert trace.spans[0].ended
        assert trace.spans[0].end_kwargs.get("level") == "ERROR"

    def test_unknown_events_ignored(self):
        tracker, trace = self._make_tracker()
        # These should not crash
        tracker.handle_event(
            {"event": "on_chain_start", "run_id": "c1", "data": {}},
            model_name="gpt-4",
        )
        tracker.handle_event(
            {"event": "on_graph_end", "run_id": "c1", "data": {"output": {"messages": []}}},
            model_name="gpt-4",
        )
        assert len(trace.generations) == 0
        assert len(trace.spans) == 0


class TestFinalize:
    """Test finalize() integration with end_rag_trace."""

    @patch("app.services.smartrag_agent.end_rag_trace")
    def test_finalize_calls_end_rag_trace(self, mock_end):
        mock_end.return_value = "trace-final-001"
        trace = FakeTrace("trace-final-001")
        ctx = FakeTraceContext(trace)
        tracker = _AgentLangfuseTracker(ctx)

        result = tracker.finalize(
            output={"answer": "42", "status": "completed"},
            status="completed",
            metadata={"run_id": "r1"},
        )
        assert result == "trace-final-001"
        mock_end.assert_called_once_with(
            ctx,
            output={"answer": "42", "status": "completed"},
            status_message="completed",
            metadata={"run_id": "r1"},
        )

    def test_finalize_disabled_returns_empty(self):
        tracker = _AgentLangfuseTracker(None)
        assert tracker.finalize(output={}, status="done") == ""


class TestFullEventSequence:
    """End-to-end test simulating a realistic agent run event sequence."""

    def test_realistic_agent_run(self):
        trace = FakeTrace("trace-e2e-001")
        ctx = FakeTraceContext(trace)
        tracker = _AgentLangfuseTracker(ctx)

        model = "deepseek-r1"

        # 1. LLM decides to call a tool
        tracker.handle_event(
            {"event": "on_chat_model_start", "run_id": "llm-1", "name": "ChatOpenAI", "data": {"input": "user question"}},
            model_name=model,
        )
        mock_chunk1 = MagicMock()
        mock_chunk1.content = ""  # tool call, no text content
        mock_chunk1.additional_kwargs = {}
        tracker.handle_event(
            {"event": "on_chat_model_stream", "run_id": "llm-1", "data": {"chunk": mock_chunk1}},
            model_name=model,
        )
        tracker.handle_event(
            {"event": "on_chat_model_end", "run_id": "llm-1", "data": {"output": None}},
            model_name=model,
        )

        # 2. Tool is called
        tracker.handle_event(
            {"event": "on_tool_start", "run_id": "tool-1", "name": "list_batches", "data": {"input": {"limit": 10}}},
            model_name=model,
        )
        tracker.handle_event(
            {"event": "on_tool_end", "run_id": "tool-1", "data": {"output": '[{"batch_id": "b1"}]'}},
            model_name=model,
        )

        # 3. LLM generates final answer
        tracker.handle_event(
            {"event": "on_chat_model_start", "run_id": "llm-2", "name": "ChatOpenAI", "data": {"input": "context"}},
            model_name=model,
        )
        mock_chunk2 = MagicMock()
        mock_chunk2.content = "Here are"
        mock_chunk2.additional_kwargs = {}
        tracker.handle_event(
            {"event": "on_chat_model_stream", "run_id": "llm-2", "data": {"chunk": mock_chunk2}},
            model_name=model,
        )
        mock_chunk3 = MagicMock()
        mock_chunk3.content = " the results."
        mock_chunk3.additional_kwargs = {}
        tracker.handle_event(
            {"event": "on_chat_model_stream", "run_id": "llm-2", "data": {"chunk": mock_chunk3}},
            model_name=model,
        )
        tracker.handle_event(
            {"event": "on_chat_model_end", "run_id": "llm-2", "data": {"output": None}},
            model_name=model,
        )

        # Verify: 2 generations (2 LLM calls), 1 tool span
        assert len(trace.generations) == 2
        assert len(trace.spans) == 1

        # All ended
        assert all(g.ended for g in trace.generations)
        assert all(s.ended for s in trace.spans)

        # Second generation captured streamed tokens
        assert trace.generations[1].end_kwargs.get("output") == "Here are the results."

        # Tool span captured output
        assert trace.spans[0].end_kwargs.get("output") == '[{"batch_id": "b1"}]'
