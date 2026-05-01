from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_langfuse_client = None
_langfuse_init_attempted = False


def langfuse_enabled() -> bool:
    return bool(
        settings.langfuse_enabled
        and settings.langfuse_public_key
        and settings.langfuse_secret_key
    )


def get_langfuse():
    global _langfuse_client, _langfuse_init_attempted
    if not langfuse_enabled():
        return None
    if _langfuse_init_attempted:
        return _langfuse_client
    _langfuse_init_attempted = True
    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("Langfuse client initialized: host=%s", settings.langfuse_host)
    except Exception:
        logger.exception("Failed to initialize Langfuse client")
        _langfuse_client = None
    return _langfuse_client


class _RagTraceContext:
    def __init__(self, trace: Any):
        self.trace = trace
        self.trace_id: str = trace.id if trace else ""

    def span(self, **kwargs: Any) -> Any | None:
        if not self.trace:
            return None
        try:
            return self.trace.span(**kwargs)
        except Exception:
            logger.debug("Langfuse span creation failed", exc_info=True)
            return None

    def generation(self, **kwargs: Any) -> Any | None:
        if not self.trace:
            return None
        try:
            return self.trace.generation(**kwargs)
        except Exception:
            logger.debug("Langfuse generation creation failed", exc_info=True)
            return None

    def update(self, **kwargs: Any) -> None:
        if not self.trace:
            return
        try:
            self.trace.update(**kwargs)
        except Exception:
            logger.debug("Langfuse trace update failed", exc_info=True)


_EMPTY_CONTEXT = _RagTraceContext(None)


def create_rag_trace(
    *,
    name: str,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    input: Any = None,
    tags: list[str] | None = None,
) -> _RagTraceContext:
    client = get_langfuse()
    if not client:
        return _EMPTY_CONTEXT
    try:
        trace = client.trace(
            name=name,
            session_id=session_id,
            metadata=metadata,
            input=input,
            tags=tags or [],
        )
        return _RagTraceContext(trace)
    except Exception:
        logger.debug("Langfuse trace creation failed", exc_info=True)
        return _EMPTY_CONTEXT


def create_rag_span(
    parent: Any,
    *,
    name: str,
    input: Any = None,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    if parent is None:
        return None
    try:
        return parent.span(name=name, input=input, metadata=metadata)
    except Exception:
        logger.debug("Langfuse span creation failed", exc_info=True)
        return None


def create_rag_generation(
    parent: Any,
    *,
    name: str,
    model: str | None = None,
    input: Any = None,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    if parent is None:
        return None
    try:
        return parent.generation(name=name, model=model, input=input, metadata=metadata)
    except Exception:
        logger.debug("Langfuse generation creation failed", exc_info=True)
        return None


def end_rag_trace(
    ctx: _RagTraceContext,
    *,
    output: Any = None,
    status_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    if not ctx.trace:
        return ""
    try:
        update_kwargs: dict[str, Any] = {}
        if output is not None:
            update_kwargs["output"] = output
        if status_message:
            update_kwargs["status_message"] = status_message
        if metadata:
            update_kwargs["metadata"] = metadata
        if update_kwargs:
            ctx.trace.update(**update_kwargs)
        client = get_langfuse()
        if client:
            client.flush()
    except Exception:
        logger.debug("Langfuse trace finalization failed", exc_info=True)
    return ctx.trace_id


def get_langchain_callback_handler(
    *,
    trace_name: str,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> tuple[Any | None, str]:
    if not langfuse_enabled():
        return None, ""
    try:
        from langfuse.callback import CallbackHandler

        handler = CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            trace_name=trace_name,
            session_id=session_id,
            metadata=metadata,
            tags=tags or [],
        )
        trace_id = handler.trace.id if hasattr(handler, "trace") and handler.trace else ""
        return handler, trace_id
    except Exception:
        logger.debug("Langfuse CallbackHandler creation failed", exc_info=True)
        return None, ""


def flush_langfuse() -> None:
    client = get_langfuse()
    if client:
        try:
            client.flush()
        except Exception:
            logger.debug("Langfuse flush failed", exc_info=True)
