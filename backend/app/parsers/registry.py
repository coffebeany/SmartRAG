from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class ParserAvailability:
    status: str
    reason: str


@dataclass(frozen=True)
class ParserStrategySpec:
    parser_name: str
    display_name: str
    description: str
    supported_file_exts: tuple[str, ...]
    capabilities: tuple[str, ...]
    config_schema: dict = field(default_factory=dict)
    default_config: dict = field(default_factory=dict)
    source: str = "autorag"
    enabled: bool = True
    loaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    required_dependencies: tuple[str, ...] = ()
    required_env_vars: tuple[str, ...] = ()
    requires_config: bool = False
    autorag_module_type: str | None = None
    autorag_parse_method: str | None = None
    executable: bool = True

    def availability(self) -> ParserAvailability:
        if not self.enabled:
            return ParserAvailability("disabled", "Parser is disabled.")
        missing_env = [name for name in self.required_env_vars if not os.getenv(name)]
        if missing_env:
            return ParserAvailability("missing_env", f"Missing environment variables: {', '.join(missing_env)}")
        if not self.executable:
            return ParserAvailability("adapter_only", "Registered for configuration; executable adapter is pending.")
        missing_deps = []
        for dependency in self.required_dependencies:
            try:
                dependency_found = importlib.util.find_spec(dependency) is not None
            except ModuleNotFoundError:
                dependency_found = False
            if not dependency_found:
                missing_deps.append(dependency)
        if missing_deps:
            return ParserAvailability("missing_dependency", f"Missing Python dependencies: {', '.join(missing_deps)}")
        if self.requires_config:
            return ParserAvailability("needs_config", "Parser requires per-run configuration.")
        return ParserAvailability("available", "Available")


class ParserRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, ParserStrategySpec] = {}

    def register(self, strategy: ParserStrategySpec) -> None:
        normalized_exts = tuple(sorted({ext.lower() for ext in strategy.supported_file_exts}))
        self._strategies[strategy.parser_name] = ParserStrategySpec(
            parser_name=strategy.parser_name,
            display_name=strategy.display_name,
            description=strategy.description,
            supported_file_exts=normalized_exts,
            capabilities=strategy.capabilities,
            config_schema=strategy.config_schema,
            default_config=strategy.default_config,
            source=strategy.source,
            enabled=strategy.enabled,
            loaded_at=strategy.loaded_at,
            required_dependencies=strategy.required_dependencies,
            required_env_vars=strategy.required_env_vars,
            requires_config=strategy.requires_config,
            autorag_module_type=strategy.autorag_module_type,
            autorag_parse_method=strategy.autorag_parse_method,
            executable=strategy.executable,
        )

    def get(self, parser_name: str) -> ParserStrategySpec | None:
        return self._strategies.get(parser_name)

    def list_enabled(self) -> list[ParserStrategySpec]:
        return sorted(
            [strategy for strategy in self._strategies.values() if strategy.enabled],
            key=lambda strategy: (strategy.autorag_module_type or "", strategy.display_name),
        )

    def supported_extensions(self) -> list[str]:
        return sorted({ext for strategy in self.list_enabled() for ext in strategy.supported_file_exts})

    def supports_extension(self, file_ext: str) -> bool:
        return file_ext.lower() in self.supported_extensions()

    def parsers_for_extension(self, file_ext: str) -> list[ParserStrategySpec]:
        normalized_ext = file_ext.lower()
        return [
            strategy
            for strategy in self.list_enabled()
            if normalized_ext in strategy.supported_file_exts
        ]

    def default_parser_for_extension(self, file_ext: str) -> ParserStrategySpec | None:
        normalized_ext = file_ext.lower()
        if normalized_ext == ".json":
            return None
        defaults = {
            ".pdf": "pdfminer",
            ".csv": "csv",
            ".md": "unstructuredmarkdown",
            ".markdown": "unstructuredmarkdown",
            ".html": "bshtml",
            ".htm": "bshtml",
            ".xml": "unstructuredxml",
            ".txt": "plain_text",
            ".log": "plain_text",
        }
        preferred = defaults.get(normalized_ext)
        if preferred:
            strategy = self.get(preferred)
            if strategy and normalized_ext in strategy.supported_file_exts:
                return strategy
        parsers = self.parsers_for_extension(normalized_ext)
        return parsers[0] if parsers else None

    def has_parser_for_extension(self, parser_name: str, file_ext: str) -> bool:
        strategy = self._strategies.get(parser_name)
        return bool(strategy and strategy.enabled and file_ext.lower() in strategy.supported_file_exts)


def schema(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or []}


TEXT_DEFAULT_CONFIG = {"encoding": "utf-8"}
PDF_DEFAULT_CONFIG = {"mode": "single"}


parser_registry = ParserRegistry()

for name, display, dependency, executable in [
    ("pdfminer", "PDFMiner", "pdfminer.high_level", True),
    ("pdfplumber", "PDFPlumber", "pdfplumber", True),
    ("pypdfium2", "PyPDFium2", "pypdfium2", True),
    ("pypdf", "PyPDF", "pypdf", True),
    ("pymupdf", "PyMuPDF", "fitz", True),
    ("unstructuredpdf", "UnstructuredPDF", "unstructured", False),
]:
    parser_registry.register(
        ParserStrategySpec(
            parser_name=name,
            display_name=f"Langchain Parse / {display}",
            description=f"AutoRAG Langchain Parse PDF method: {display}.",
            supported_file_exts=(".pdf",),
            capabilities=("pdf", "autorag", "langchain_parse"),
            config_schema=schema({"mode": {"type": "string", "enum": ["single", "page"]}}),
            default_config=PDF_DEFAULT_CONFIG,
            required_dependencies=(dependency,),
            executable=executable,
            autorag_module_type="langchain_parse",
            autorag_parse_method=name,
        )
    )

parser_registry.register(
    ParserStrategySpec(
        parser_name="csv",
        display_name="Langchain Parse / CSV",
        description="AutoRAG Langchain Parse CSV method.",
        supported_file_exts=(".csv",),
        capabilities=("csv", "table", "autorag", "langchain_parse"),
        config_schema=schema({"encoding": {"type": "string"}}),
        default_config=TEXT_DEFAULT_CONFIG,
        autorag_module_type="langchain_parse",
        autorag_parse_method="csv",
    )
)

parser_registry.register(
    ParserStrategySpec(
        parser_name="json",
        display_name="Langchain Parse / JSON",
        description="AutoRAG Langchain Parse JSON method. Requires jq_schema.",
        supported_file_exts=(".json",),
        capabilities=("json", "autorag", "langchain_parse"),
        config_schema=schema({"jq_schema": {"type": "string"}}, required=["jq_schema"]),
        default_config={"encoding": "utf-8", "jq_schema": ""},
        requires_config=True,
        autorag_module_type="langchain_parse",
        autorag_parse_method="json",
    )
)

for name, display, exts in [
    ("unstructuredmarkdown", "UnstructuredMarkdown", (".md", ".markdown")),
    ("bshtml", "BSHTML", (".html", ".htm")),
    ("unstructuredxml", "UnstructuredXML", (".xml",)),
]:
    parser_registry.register(
        ParserStrategySpec(
            parser_name=name,
            display_name=f"Langchain Parse / {display}",
            description=f"AutoRAG Langchain Parse text method: {display}.",
            supported_file_exts=exts,
            capabilities=("text", "autorag", "langchain_parse"),
            config_schema=schema({"encoding": {"type": "string"}}),
            default_config=TEXT_DEFAULT_CONFIG,
            autorag_module_type="langchain_parse",
            autorag_parse_method=name,
        )
    )

for name, env_vars, description in [
    ("directory", (), "AutoRAG all_files directory parser."),
    ("unstructured", (), "AutoRAG all_files Unstructured parser."),
    ("upstagedocumentparse", ("UPSTAGE_API_KEY",), "AutoRAG all_files Upstage Document Parse."),
]:
    parser_registry.register(
        ParserStrategySpec(
            parser_name=name,
            display_name=f"Langchain Parse / {name}",
            description=description,
            supported_file_exts=(".pdf", ".csv", ".json", ".md", ".markdown", ".html", ".htm", ".xml", ".txt"),
            capabilities=("all_files", "autorag", "langchain_parse"),
            config_schema=schema({"parse_method": {"type": "string"}}),
            default_config={"parse_method": "auto"},
            required_env_vars=env_vars,
            executable=False,
            autorag_module_type="langchain_parse",
            autorag_parse_method=name,
        )
    )

parser_registry.register(
    ParserStrategySpec(
        parser_name="llama_parse",
        display_name="Llama Parse",
        description="AutoRAG Llama Parse for complex PDFs, tables, and multimodal parsing.",
        supported_file_exts=(".pdf", ".docx", ".pptx", ".html", ".md"),
        capabilities=("cloud", "layout", "table", "autorag"),
        config_schema=schema(
            {
                "result_type": {"type": "string", "enum": ["text", "markdown", "json"]},
                "language": {"type": "string"},
                "use_vendor_multimodal_model": {"type": "boolean"},
                "vendor_multimodal_model_name": {"type": "string"},
            }
        ),
        default_config={"result_type": "markdown", "language": "en"},
        required_env_vars=("LLAMA_CLOUD_API_KEY",),
        executable=False,
        autorag_module_type="llama_parse",
    )
)

parser_registry.register(
    ParserStrategySpec(
        parser_name="clova",
        display_name="Clova OCR",
        description="AutoRAG Clova OCR parser for OCR and table detection.",
        supported_file_exts=(".pdf", ".png", ".jpg", ".jpeg"),
        capabilities=("ocr", "table", "cloud", "autorag"),
        config_schema=schema({"table_detection": {"type": "boolean"}}),
        default_config={"table_detection": True},
        required_env_vars=("CLOVA_OCR_API_URL", "CLOVA_OCR_SECRET_KEY"),
        executable=False,
        autorag_module_type="clova",
    )
)

parser_registry.register(
    ParserStrategySpec(
        parser_name="table_hybrid_parse",
        display_name="Table Hybrid Parse",
        description="AutoRAG hybrid table parser that routes page regions to text and table parsers.",
        supported_file_exts=(".pdf",),
        capabilities=("table", "hybrid", "autorag"),
        config_schema=schema(
            {
                "text_parse_module": {"type": "string"},
                "text_params": {"type": "object"},
                "table_parse_module": {"type": "string"},
                "table_params": {"type": "object"},
            },
            required=["text_parse_module", "table_parse_module"],
        ),
        default_config={
            "text_parse_module": "pdfminer",
            "text_params": PDF_DEFAULT_CONFIG,
            "table_parse_module": "pdfplumber",
            "table_params": {},
        },
        required_dependencies=("pdfplumber",),
        requires_config=True,
        executable=False,
        autorag_module_type="table_hybrid_parse",
    )
)

parser_registry.register(
    ParserStrategySpec(
        parser_name="plain_text",
        display_name="Plain Text",
        description="SmartRAG lightweight parser for TXT and log files.",
        supported_file_exts=(".txt", ".log"),
        capabilities=("text", "fast", "local"),
        config_schema=schema({"encoding": {"type": "string"}}),
        default_config=TEXT_DEFAULT_CONFIG,
        source="built_in",
    )
)
