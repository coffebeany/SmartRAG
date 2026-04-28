from datetime import UTC, datetime

from app.core.security import encrypt_secret
from app.models.entities import ComponentConfig
from app.rag.registry import rag_component_registry
from app.services.rag import (
    Passage,
    _bm25_scores,
    _config_out,
    _filter,
    _hybrid_cc,
    _hybrid_rrf,
    _normalize_scores,
    _query_expansion_summary,
    _retrieval_candidate_top_ks,
    _render_agent_prompt,
    _tokenize_bm25,
    _trace,
)


def test_rag_component_registry_contains_autorag_modules() -> None:
    by_node = {}
    for component in rag_component_registry.list():
        by_node.setdefault(component.node_type, set()).add(component.module_type)

    assert {"query_decompose", "hyde", "multi_query_expansion", "pass_query_expansion"}.issubset(
        by_node["query_expansion"]
    )
    assert {"bm25", "vectordb", "hybrid_rrf", "hybrid_cc"}.issubset(by_node["retrieval"])
    assert {"prev_next_augmenter", "pass_passage_augmenter"}.issubset(by_node["passage_augmenter"])
    assert {"cohere_reranker", "rankgpt", "flashrank_reranker", "pass_reranker"}.issubset(
        by_node["passage_reranker"]
    )
    assert {"similarity_threshold_cutoff", "recency_filter", "pass_passage_filter"}.issubset(
        by_node["passage_filter"]
    )
    assert {"tree_summarize", "refine", "longllmlingua", "pass_compressor"}.issubset(
        by_node["passage_compressor"]
    )
    assert {"llm_answer"}.issubset(by_node["answer_generator"])


def test_rag_component_registry_exposes_form_schema_and_install_hints() -> None:
    hyde = rag_component_registry.get("query_expansion", "hyde")
    cohere = rag_component_registry.get("passage_reranker", "cohere_reranker")
    flashrank = rag_component_registry.get("passage_reranker", "flashrank_reranker")
    tree_summarize = rag_component_registry.get("passage_compressor", "tree_summarize")
    llm_answer = rag_component_registry.get("answer_generator", "llm_answer")

    assert hyde is not None
    assert hyde.default_config["max_output_tokens"] == 512
    assert hyde.llm_config_mode == "agent_profile_required"
    assert "model_id" not in hyde.config_schema["properties"]
    assert hyde.config_schema["required"] == ["agent_id"]
    pass_query = rag_component_registry.get("query_expansion", "pass_query_expansion")
    assert pass_query is not None
    assert pass_query.llm_config_mode == "none"
    assert not {"model_id", "agent_id"}.intersection(pass_query.config_schema["properties"])
    assert cohere is not None
    assert "api_key" not in cohere.config_schema["properties"]
    assert cohere.secret_config_schema["required"] == ["api_key"]
    assert cohere.availability().status == "needs_config"
    assert flashrank is not None
    assert flashrank.optional_dependency_extra == "rag-rerank-local"
    assert tree_summarize is not None
    assert tree_summarize.default_config["max_output_tokens"] == 1024
    assert tree_summarize.llm_config_mode == "agent_profile_required"
    assert "model_id" not in tree_summarize.config_schema["properties"]
    assert llm_answer is not None
    assert llm_answer.requires_llm is True
    assert llm_answer.default_config["max_output_tokens"] == 1024
    assert llm_answer.llm_config_mode == "agent_profile_required"
    assert "model_id" not in llm_answer.config_schema["properties"]
    hybrid_rrf = rag_component_registry.get("retrieval", "hybrid_rrf")
    assert hybrid_rrf is not None
    assert {"bm25_top_k", "vectordb_top_k"}.issubset(hybrid_rrf.config_schema["properties"])
    assert hybrid_rrf.default_config["bm25_top_k"] == 10
    assert hybrid_rrf.default_config["vectordb_top_k"] == 10


def test_component_config_masks_secret_and_reports_availability() -> None:
    row = ComponentConfig(
        config_id="config-1",
        node_type="passage_reranker",
        module_type="cohere_reranker",
        display_name="Cohere Reranker",
        config={"model": "rerank-v3.5"},
        secret_config_encrypted=encrypt_secret('{"api_key": "cohere-secret-key"}'),
        enabled=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    output = _config_out(row)

    assert output.secret_config_masked["api_key"] == "coh****-key"
    assert output.availability_status == "available"


def test_agent_query_expansion_prompt_is_template_plus_original_query() -> None:
    rendered = _render_agent_prompt(
        "请提炼核心问题。",
        "Generate diverse retrieval queries.\n\nQuery: 大语言模型的核心概念是什么？",
        "大语言模型的核心概念是什么？",
    )

    assert rendered == (
        "请提炼核心问题。\n\n"
        "用户原始提问：\n大语言模型的核心概念是什么？\n\n"
        "当前节点输入：\nGenerate diverse retrieval queries.\n\nQuery: 大语言模型的核心概念是什么？"
    )
    assert "Generate diverse retrieval queries" in rendered


def test_query_expansion_summary_separates_raw_output_from_display_queries() -> None:
    summary = _query_expansion_summary(
        "呃。。。我想问，，嗯，，，大语言模型，它，它的核心概念是什么？",
        [
            "呃。。。我想问，，嗯，，，大语言模型，它，它的核心概念是什么？",
            "大语言模型的核心概念是什么？",
        ],
        "大语言模型的核心概念是什么？",
    )

    assert "queries" not in summary
    assert summary["original_query"] == "呃。。。我想问，，嗯，，，大语言模型，它，它的核心概念是什么？"
    assert summary["expanded_queries"] == ["大语言模型的核心概念是什么？"]
    assert summary["raw_output"] == "大语言模型的核心概念是什么？"


def test_bm25_tokenizer_and_scores_rank_matching_document() -> None:
    documents = [
        _tokenize_bm25("large language model transformer", "simple"),
        _tokenize_bm25("database index transaction", "simple"),
    ]
    scores = _bm25_scores(_tokenize_bm25("language model", "simple"), documents)

    assert scores[0] > scores[1]
    assert _tokenize_bm25("大语言模型", "simple") == ["大", "语", "言", "模", "型"]


def test_hybrid_rrf_combines_lexical_and_semantic_rankings() -> None:
    lexical = [[Passage(chunk_id="a", contents="alpha", score=3, metadata={"matched_queries": ["q"], "source_scores": {"lexical": 3}})]]
    semantic = [[Passage(chunk_id="b", contents="beta", score=0.9, metadata={"matched_queries": ["q"], "source_scores": {"semantic": 0.9}})]]

    output = _hybrid_rrf(lexical, semantic, {"lexical_weight": 1, "semantic_weight": 1, "rrf_k": 60}, 2)

    assert [item.chunk_id for item in output] == ["a", "b"]
    assert output[0].metadata["retrieval_module"] == "hybrid_rrf"


def test_hybrid_retrieval_candidate_top_k_can_differ_from_final_top_k() -> None:
    assert _retrieval_candidate_top_ks("hybrid_rrf", {"bm25_top_k": 20, "vectordb_top_k": 30}, 5) == (20, 30)
    assert _retrieval_candidate_top_ks("hybrid_cc", {}, 5) == (5, 5)
    assert _retrieval_candidate_top_ks("vectordb", {"bm25_top_k": 20, "vectordb_top_k": 30}, 5) == (5, 5)


def test_hybrid_cc_normalizes_and_applies_weights() -> None:
    lexical = [[
        Passage(chunk_id="a", contents="alpha", score=10, metadata={"matched_queries": ["q"]}),
        Passage(chunk_id="b", contents="beta", score=1, metadata={"matched_queries": ["q"]}),
    ]]
    semantic = [[Passage(chunk_id="b", contents="beta", score=0.9, metadata={"matched_queries": ["q"]})]]

    output = _hybrid_cc(lexical, semantic, {"lexical_weight": 0.2, "semantic_weight": 0.8, "normalize_method": "mm"}, 2)

    assert output[0].chunk_id == "b"
    assert output[0].metadata["retrieval_module"] == "hybrid_cc"
    assert _normalize_scores([1, 2, 3], "mm") == [0.0, 0.5, 1.0]


def test_passage_filter_threshold_and_trace_shape() -> None:
    passages = [
        Passage(chunk_id="a", contents="alpha", score=0.9),
        Passage(chunk_id="b", contents="beta", score=0.2),
    ]

    filtered, event = _filter(
        passages,
        {"node_type": "passage_filter", "module_type": "similarity_threshold_cutoff"},
        {"threshold": 0.5},
    )

    assert [item.chunk_id for item in filtered] == ["a"]
    assert event["node_type"] == "passage_filter"
    assert event["activated"] is True
    assert event["output_summary"]["passage_count"] == 1


def test_trace_event_contains_required_fields() -> None:
    event = _trace(
        node_type="retrieval",
        module_type="chroma",
        started=0,
        activated=True,
        input_summary={"top_k": 5},
        output_summary={"passage_count": 2},
    )

    assert {"node_type", "module_type", "status", "activated", "input_summary", "output_summary", "latency_ms", "error"}.issubset(event)
