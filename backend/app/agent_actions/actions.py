from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.agent_actions.registry import AgentActionContext, EmptyActionInput, smartrag_action
from app.models.entities import EvaluationReportItem
from app.schemas.chunks import ChunkRunCreate
from app.schemas.evaluations import (
    EvaluationDatasetItemCreate,
    EvaluationDatasetItemUpdate,
    EvaluationDatasetRunCreate,
    EvaluationReportRunCreate,
    ParseEvaluationRunCreate,
)
from app.schemas.materials import (
    MaterialBatchCreate,
    MaterialBatchUpdate,
    ParseRunCreate,
    ProcessingDefaultRulesUpdate,
)
from app.schemas.rag import (
    ComponentConfigCreate,
    ComponentConfigUpdate,
    RagFlowCreate,
    RagFlowRunCreate,
    RagFlowUpdate,
)
from app.schemas.vectors import VectorRunCreate
from app.services import chunks, evaluations, materials, parse_runs, rag, vectors


OBJECT_SCHEMA = {"type": "object"}
LIST_SCHEMA = {"type": "array"}


class BatchIdInput(BaseModel):
    batch_id: str = Field(description="Material batch identifier.")


class RunIdInput(BaseModel):
    run_id: str = Field(description="Run identifier.")


class BatchRunInput(BaseModel):
    batch_id: str
    run_id: str


class ParsePlanInput(BaseModel):
    batch_id: str


class ChunkPlanInput(BaseModel):
    batch_id: str
    parse_run_id: str


class VectorPlanInput(BaseModel):
    batch_id: str
    chunk_run_id: str


class FileRunPageInput(BaseModel):
    run_id: str
    file_run_id: str
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=500)


class FileRunInput(BaseModel):
    run_id: str
    file_run_id: str


class RemoveMaterialFileInput(BaseModel):
    batch_id: str
    file_id: str
    created_by: str | None = None


class UploadFromPathsInput(BaseModel):
    batch_id: str
    file_paths: list[str] = Field(min_length=1)
    created_by: str | None = None


class ListComponentConfigsInput(BaseModel):
    node_type: str | None = None


class ConfigIdInput(BaseModel):
    config_id: str


class RagComponentInput(BaseModel):
    node_type: str | None = None


class FlowIdInput(BaseModel):
    flow_id: str


class RunRagFlowInput(BaseModel):
    flow_id: str
    query: str = Field(min_length=1)


class DatasetItemPageInput(BaseModel):
    run_id: str
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=500)


class DatasetItemInput(BaseModel):
    run_id: str
    item_id: str


class FailureCasesInput(BaseModel):
    report_run_id: str
    limit: int = Field(default=50, ge=1, le=500)


class CreateMaterialBatchInput(MaterialBatchCreate):
    pass


class UpdateMaterialBatchInput(MaterialBatchUpdate):
    batch_id: str


class CreateParseRunInput(ParseRunCreate):
    pass


class CreateChunkRunInput(ChunkRunCreate):
    pass


class CreateVectorRunInput(VectorRunCreate):
    pass


class CreateComponentConfigInput(ComponentConfigCreate):
    pass


class UpdateComponentConfigInput(ComponentConfigUpdate):
    config_id: str


class CreateRagFlowInput(RagFlowCreate):
    pass


class UpdateRagFlowInput(RagFlowUpdate):
    flow_id: str


class ParseEvaluationInput(ParseEvaluationRunCreate):
    pass


class CreateEvaluationDatasetRunInput(EvaluationDatasetRunCreate):
    pass


class CreateEvaluationDatasetItemInput(EvaluationDatasetItemCreate):
    run_id: str


class UpdateEvaluationDatasetItemInput(EvaluationDatasetItemUpdate):
    run_id: str
    item_id: str


class CreateEvaluationReportRunInput(EvaluationReportRunCreate):
    pass


class _PathUpload:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.filename = path.name
        self.content_type = None

    async def read(self) -> bytes:
        return self.path.read_bytes()


def _started(run_id: str, kind: str) -> dict[str, str]:
    return {
        "run_id": run_id,
        "status": "pending",
        "note": f"{kind} run was created and scheduled in the background. Poll the run detail action for progress.",
    }


@smartrag_action(name="list_material_batches", title="List material batches", output_schema=LIST_SCHEMA, tags=["materials"])
async def list_material_batches(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """List material batches.

    Use when the agent needs the available material collections before selecting files, parse runs, chunk runs, vector runs, or evaluation inputs. Takes no input and returns batch metadata including ids, names, descriptions, version and file count. Fails only when the database is unavailable.
    """
    return await materials.list_batches(ctx.session)


@smartrag_action(name="create_material_batch", title="Create material batch", input_model=CreateMaterialBatchInput, output_schema=OBJECT_SCHEMA, permission_scope="materials:write", tags=["materials"])
async def create_material_batch(ctx: AgentActionContext, payload: CreateMaterialBatchInput) -> Any:
    """Create a material batch.

    Use when new source documents should be grouped before upload or processing. Provide a non-empty batch_name and optional description/project metadata. Returns the created batch id and version metadata. Fails if validation fails or the database rejects the insert.
    """
    return await materials.create_batch(ctx.session, MaterialBatchCreate.model_validate(payload.model_dump()))


@smartrag_action(name="get_material_batch", title="Get material batch", input_model=BatchIdInput, output_schema=OBJECT_SCHEMA, tags=["materials"], resource_uri_template="smartrag://material-batches/{batch_id}/summary")
async def get_material_batch(ctx: AgentActionContext, payload: BatchIdInput) -> Any:
    """Get one material batch.

    Use when the agent needs exact metadata for a known batch_id. Returns batch identity, version, file count and timestamps. Fails with not found if the batch_id does not exist.
    """
    batch = await materials.get_batch(ctx.session, payload.batch_id)
    from app.schemas.materials import MaterialBatchOut

    return MaterialBatchOut.model_validate(batch, from_attributes=True)


@smartrag_action(name="update_material_batch", title="Update material batch", input_model=UpdateMaterialBatchInput, output_schema=OBJECT_SCHEMA, permission_scope="materials:write", is_destructive=True, tags=["materials"])
async def update_material_batch(ctx: AgentActionContext, payload: UpdateMaterialBatchInput) -> Any:
    """Update a material batch.

    Use only when the user asked to rename or edit a batch description. batch_id must identify an existing batch. Returns updated batch metadata. Fails when the batch does not exist or the payload is invalid.
    """
    data = payload.model_dump()
    batch_id = data.pop("batch_id")
    return await materials.update_batch(ctx.session, batch_id, MaterialBatchUpdate.model_validate(data))


@smartrag_action(name="delete_material_batch", title="Delete material batch", input_model=BatchIdInput, output_schema=OBJECT_SCHEMA, permission_scope="materials:delete", is_destructive=True, tags=["materials"])
async def delete_material_batch(ctx: AgentActionContext, payload: BatchIdInput) -> dict[str, Any]:
    """Delete a material batch.

    Use only after explicit user intent to remove a whole batch and its dependent records. Returns deleted=true and batch_id. Fails if the batch does not exist or storage cleanup fails.
    """
    await materials.delete_batch(ctx.session, payload.batch_id)
    return {"deleted": True, "batch_id": payload.batch_id}


@smartrag_action(name="list_material_files", title="List material files", input_model=BatchIdInput, output_schema=LIST_SCHEMA, tags=["materials"])
async def list_material_files(ctx: AgentActionContext, payload: BatchIdInput) -> Any:
    """List files in a material batch.

    Use before parse planning or file removal to inspect active and removed files. batch_id is required. Returns file ids, original filenames, extensions, storage URIs, checksums and status. Fails if the batch does not exist.
    """
    return await materials.list_files(ctx.session, payload.batch_id)


@smartrag_action(name="upload_material_files_from_paths", title="Upload material files from paths", input_model=UploadFromPathsInput, output_schema=OBJECT_SCHEMA, permission_scope="materials:write", tags=["materials"])
async def upload_material_files_from_paths(ctx: AgentActionContext, payload: UploadFromPathsInput) -> Any:
    """Upload local files into a material batch.

    Use when a trusted agent or MCP client has local file paths available on the backend machine. file_paths must exist and must use supported parser extensions. Returns created file records, new batch version and duplicate checksums. Fails for missing paths, unsupported extensions, or duplicate validation issues.
    """
    uploads = []
    for value in payload.file_paths:
        path = Path(value).expanduser()
        if not path.exists() or not path.is_file():
            raise ValueError(f"File path does not exist or is not a file: {value}")
        uploads.append(_PathUpload(path))
    return await materials.upload_files(ctx.session, payload.batch_id, uploads, payload.created_by)


@smartrag_action(name="remove_material_file", title="Remove material file", input_model=RemoveMaterialFileInput, output_schema=OBJECT_SCHEMA, permission_scope="materials:delete", is_destructive=True, tags=["materials"])
async def remove_material_file(ctx: AgentActionContext, payload: RemoveMaterialFileInput) -> Any:
    """Remove one file from a material batch.

    Use only when the user asked to remove a specific file_id from a batch. This creates a new batch version and marks the file removed instead of deleting history. Returns the new version record. Fails if the file is missing or already removed.
    """
    return await materials.remove_file(ctx.session, payload.batch_id, payload.file_id, payload.created_by)


@smartrag_action(name="list_material_versions", title="List material versions", input_model=BatchIdInput, output_schema=LIST_SCHEMA, tags=["materials"])
async def list_material_versions(ctx: AgentActionContext, payload: BatchIdInput) -> Any:
    """List material batch versions.

    Use when the agent needs to understand file additions/removals over time. batch_id is required. Returns version records with added, removed and active file snapshots. Fails if the batch does not exist.
    """
    return await materials.list_versions(ctx.session, payload.batch_id)


@smartrag_action(name="list_processing_default_rules", title="List processing default rules", output_schema=LIST_SCHEMA, tags=["materials", "rules"])
async def list_processing_default_rules(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """List default processing rules.

    Use to inspect parser/chunker defaults per file extension before creating parse or chunk runs. Takes no input. Returns rule ids, extensions, parser names, parser config text and enabled flags. Fails if rule initialization or database access fails.
    """
    return await materials.list_processing_rules(ctx.session)


@smartrag_action(name="update_processing_default_rules", title="Update processing default rules", input_model=ProcessingDefaultRulesUpdate, output_schema=LIST_SCHEMA, permission_scope="rules:write", is_destructive=True, tags=["materials", "rules"])
async def update_processing_default_rules(ctx: AgentActionContext, payload: ProcessingDefaultRulesUpdate) -> Any:
    """Update default processing rules.

    Use only when the user asks to change default parser/chunker settings for file extensions. Each rule must reference a supported extension and known parser/chunker. Returns the full updated rule list. Fails on unsupported extensions, unknown strategies or invalid payloads.
    """
    return await materials.update_processing_rules(ctx.session, payload)


@smartrag_action(name="list_parser_strategies", title="List parser strategies", output_schema=LIST_SCHEMA, tags=["parse"])
async def list_parser_strategies(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """List available parser strategies.

    Use before making a parse plan or selecting parser_name values. Returns each parser's supported extensions, config schema, default config, availability and requirements. Fails only when registry inspection fails.
    """
    return await parse_runs.list_parser_strategies()


@smartrag_action(name="refresh_parser_strategies", title="Refresh parser strategies", output_schema=LIST_SCHEMA, permission_scope="parse:write", tags=["parse"])
async def refresh_parser_strategies(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """Refresh parser strategy discovery.

    Use after parser plugins or optional dependencies changed. Takes no input and returns the currently enabled parser strategies. This has a registry cache side effect but does not modify persisted user data. Fails when strategy discovery fails.
    """
    return await materials.refresh_parser_strategies(ctx.session)


@smartrag_action(name="get_parse_plan", title="Get parse plan", input_model=ParsePlanInput, output_schema=OBJECT_SCHEMA, tags=["parse"])
async def get_parse_plan(ctx: AgentActionContext, payload: ParsePlanInput) -> Any:
    """Get parse plan for a batch.

    Use before creating a parse run to choose parser selections for active files. batch_id is required. Returns files, default parser names/configs and parser options. Fails if the batch does not exist.
    """
    return await parse_runs.get_parse_plan(ctx.session, payload.batch_id)


@smartrag_action(name="create_parse_run", title="Create parse run", input_model=CreateParseRunInput, output_schema=OBJECT_SCHEMA, permission_scope="parse:write", tags=["parse"])
async def create_parse_run(ctx: AgentActionContext, payload: CreateParseRunInput) -> dict[str, Any]:
    """Create and start a parse run.

    Use after get_parse_plan when parser selections are known. batch_id and files selections are required. Returns run_id and scheduling status for a background parse task. Fails if selected files or parser configs are invalid.
    """
    run = await parse_runs.create_parse_run(ctx.session, payload)
    asyncio.create_task(parse_runs.execute_parse_run(run.run_id))
    return _started(run.run_id, "parse")


@smartrag_action(name="list_parse_runs", title="List parse runs", output_schema=LIST_SCHEMA, tags=["parse"])
async def list_parse_runs(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """List parse runs.

    Use to inspect recent parse tasks and choose a completed parse_run_id for chunking. Returns run ids, batch ids, status counters, timestamps and error summaries. Fails only when database access fails.
    """
    return await parse_runs.list_parse_runs(ctx.session)


@smartrag_action(name="get_parse_run", title="Get parse run", input_model=RunIdInput, output_schema=OBJECT_SCHEMA, tags=["parse"], resource_uri_template="smartrag://parse-runs/{run_id}/summary")
async def get_parse_run(ctx: AgentActionContext, payload: RunIdInput) -> Any:
    """Get parse run summary.

    Use to poll parse progress or verify completion before chunking. run_id is required. Returns status, file counters, error summary and timestamps. Fails if the run does not exist.
    """
    return await parse_runs.get_parse_run(ctx.session, payload.run_id)


@smartrag_action(name="delete_parse_run", title="Delete parse run", input_model=RunIdInput, output_schema=OBJECT_SCHEMA, permission_scope="parse:delete", is_destructive=True, tags=["parse"])
async def delete_parse_run(ctx: AgentActionContext, payload: RunIdInput) -> dict[str, Any]:
    """Delete a parse run and artifacts.

    Use only after explicit user intent to remove parsed outputs. run_id is required. Returns deleted=true and run_id. Fails if the run does not exist or artifact cleanup is unsafe.
    """
    await parse_runs.delete_parse_run(ctx.session, payload.run_id)
    return {"deleted": True, "run_id": payload.run_id}


@smartrag_action(name="list_parse_file_runs", title="List parse file runs", input_model=RunIdInput, output_schema=LIST_SCHEMA, tags=["parse"])
async def list_parse_file_runs(ctx: AgentActionContext, payload: RunIdInput) -> Any:
    """List per-file parse results for a parse run.

    Use when inspecting which files parsed successfully or choosing a file_run_id for detailed parsed document inspection. run_id is required. Returns per-file status, parser, latency and output artifact metadata. Fails if the run does not exist.
    """
    return await parse_runs.list_parse_file_runs(ctx.session, payload.run_id)


@smartrag_action(name="get_parse_file_run_detail", title="Get parsed document detail", input_model=FileRunInput, output_schema=OBJECT_SCHEMA, tags=["parse"], resource_uri_template="smartrag://parse-runs/{run_id}/files/{file_run_id}/detail")
async def get_parse_file_run_detail(ctx: AgentActionContext, payload: FileRunInput) -> Any:
    """Get one parse file run detail.

    Use when the agent needs parsed text metadata for one file. run_id and file_run_id are required. Returns file run metadata and parsed document if available. Fails if the file run does not exist.
    """
    return await parse_runs.get_parse_file_run_detail(ctx.session, payload.run_id, payload.file_run_id)


@smartrag_action(name="get_parse_file_run_elements", title="Get parsed document elements", input_model=FileRunPageInput, output_schema=OBJECT_SCHEMA, tags=["parse"])
async def get_parse_file_run_elements(ctx: AgentActionContext, payload: FileRunPageInput) -> Any:
    """Get parsed elements for one file run.

    Use for paged inspection of parser output structure without loading the full document. run_id and file_run_id are required; offset and limit control pagination. Returns element items and page metadata. Fails if the file run does not exist.
    """
    return await parse_runs.get_parse_file_run_elements(ctx.session, payload.run_id, payload.file_run_id, payload.offset, payload.limit)


@smartrag_action(name="list_chunker_strategies", title="List chunker strategies", output_schema=LIST_SCHEMA, tags=["chunk"])
async def list_chunker_strategies(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """List available chunker strategies.

    Use before creating a chunk run to select chunker_name and understand config schema. Returns strategy metadata, default config, capabilities, dependency requirements and availability. Fails only when registry inspection fails.
    """
    return await chunks.list_chunk_strategies()


@smartrag_action(name="refresh_chunker_strategies", title="Refresh chunker strategies", output_schema=LIST_SCHEMA, permission_scope="chunk:write", tags=["chunk"])
async def refresh_chunker_strategies(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """Refresh chunker strategy discovery.

    Use after chunker plugins or optional dependencies changed. Takes no input and returns enabled chunker strategies. This has a registry cache side effect but does not modify persisted user data. Fails when strategy discovery fails.
    """
    return await chunks.refresh_chunk_strategies()


@smartrag_action(name="get_chunk_plan", title="Get chunk plan", input_model=ChunkPlanInput, output_schema=OBJECT_SCHEMA, tags=["chunk"])
async def get_chunk_plan(ctx: AgentActionContext, payload: ChunkPlanInput) -> Any:
    """Get chunking plan.

    Use after a parse run completes to inspect parsed documents and chunker options. batch_id and parse_run_id are required and must belong together. Returns parsed file summaries and available chunkers. Fails if parse run is not completed.
    """
    return await chunks.get_chunk_plan(ctx.session, payload.batch_id, payload.parse_run_id)


@smartrag_action(name="create_chunk_run", title="Create chunk run", input_model=CreateChunkRunInput, output_schema=OBJECT_SCHEMA, permission_scope="chunk:write", tags=["chunk"])
async def create_chunk_run(ctx: AgentActionContext, payload: CreateChunkRunInput) -> dict[str, Any]:
    """Create and start a chunk run.

    Use after get_chunk_plan when chunker_name and chunker_config are known. Returns run_id and scheduling status for a background chunk task. Fails if parse run is incomplete, chunker is unknown, or config is missing required fields.
    """
    run = await chunks.create_chunk_run(ctx.session, payload)
    asyncio.create_task(chunks.execute_chunk_run(run.run_id))
    return _started(run.run_id, "chunk")


@smartrag_action(name="list_chunk_runs", title="List chunk runs", output_schema=LIST_SCHEMA, tags=["chunk"])
async def list_chunk_runs(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """List chunk runs.

    Use to inspect recent chunk tasks and choose a completed chunk_run_id for vectorization or evaluation dataset generation. Returns run ids, status counters, stats and timestamps. Fails only when database access fails.
    """
    return await chunks.list_chunk_runs(ctx.session)


@smartrag_action(name="get_chunk_run", title="Get chunk run", input_model=RunIdInput, output_schema=OBJECT_SCHEMA, tags=["chunk"], resource_uri_template="smartrag://chunk-runs/{run_id}/summary")
async def get_chunk_run(ctx: AgentActionContext, payload: RunIdInput) -> Any:
    """Get chunk run summary.

    Use to poll chunk progress or verify completion before vectorization. run_id is required. Returns status, file counters, chunk stats, artifact URI and errors. Fails if the run does not exist.
    """
    return await chunks.get_chunk_run(ctx.session, payload.run_id)


@smartrag_action(name="delete_chunk_run", title="Delete chunk run", input_model=RunIdInput, output_schema=OBJECT_SCHEMA, permission_scope="chunk:delete", is_destructive=True, tags=["chunk"])
async def delete_chunk_run(ctx: AgentActionContext, payload: RunIdInput) -> dict[str, Any]:
    """Delete a chunk run and artifacts.

    Use only after explicit user intent to remove chunks. run_id is required. Returns deleted=true and run_id. Fails if the run does not exist or artifact cleanup is unsafe.
    """
    await chunks.delete_chunk_run(ctx.session, payload.run_id)
    return {"deleted": True, "run_id": payload.run_id}


@smartrag_action(name="list_chunk_file_runs", title="List chunk file runs", input_model=RunIdInput, output_schema=LIST_SCHEMA, tags=["chunk"])
async def list_chunk_file_runs(ctx: AgentActionContext, payload: RunIdInput) -> Any:
    """List per-file chunk results.

    Use when inspecting which parsed files chunked successfully or choosing a file_run_id for chunk inspection. run_id is required. Returns per-file status, chunk counts, latency and errors. Fails if the run does not exist.
    """
    return await chunks.list_chunk_file_runs(ctx.session, payload.run_id)


@smartrag_action(name="get_chunk_file_run", title="Get chunk file run", input_model=FileRunInput, output_schema=OBJECT_SCHEMA, tags=["chunk"])
async def get_chunk_file_run(ctx: AgentActionContext, payload: FileRunInput) -> Any:
    """Get one chunk file run.

    Use when the agent needs status and metadata for one chunked file. run_id and file_run_id are required. Returns per-file chunk status and counts. Fails if the file run does not exist.
    """
    return await chunks.get_chunk_file_run(ctx.session, payload.run_id, payload.file_run_id)


@smartrag_action(name="get_chunk_file_run_chunks", title="Inspect chunks", input_model=FileRunPageInput, output_schema=OBJECT_SCHEMA, tags=["chunk"], resource_uri_template="smartrag://chunk-runs/{run_id}/files/{file_run_id}/chunks")
async def get_chunk_file_run_chunks(ctx: AgentActionContext, payload: FileRunPageInput) -> Any:
    """Inspect chunks for one file run.

    Use for paged inspection of chunk contents and metadata. run_id and file_run_id are required; offset and limit control pagination. Returns chunk items and page metadata. Fails if the file run does not exist.
    """
    return await chunks.get_chunk_file_run_chunks(ctx.session, payload.run_id, payload.file_run_id, payload.offset, payload.limit)


@smartrag_action(name="compare_chunk_runs", title="Compare chunk runs", input_model=BatchIdInput, output_schema=LIST_SCHEMA, tags=["chunk"])
async def compare_chunk_runs(ctx: AgentActionContext, payload: BatchIdInput) -> Any:
    """Compare chunk runs in a batch.

    Use when selecting the best chunking configuration or comparing stats across runs. batch_id is required. Returns run-level stats and configs for all chunk runs in the batch. Fails if the batch does not exist.
    """
    return await chunks.compare_batch_chunk_runs(ctx.session, payload.batch_id)


@smartrag_action(name="list_vectordbs", title="List vector databases", output_schema=LIST_SCHEMA, tags=["vector"])
async def list_vectordbs(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """List available vector database adapters.

    Use before vectorization to choose vectordb_name and inspect config schema. Returns adapter metadata, default config, advanced options, capabilities and availability. Fails only when registry inspection fails.
    """
    return await vectors.list_vectordbs()


@smartrag_action(name="refresh_vectordbs", title="Refresh vector databases", output_schema=LIST_SCHEMA, permission_scope="vector:write", tags=["vector"])
async def refresh_vectordbs(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """Refresh vector database adapter discovery.

    Use after vector store plugins or optional dependencies changed. Takes no input and returns enabled adapters. This has a registry cache side effect but does not modify persisted user data. Fails when adapter discovery fails.
    """
    return await vectors.refresh_vectordbs()


@smartrag_action(name="get_vector_plan", title="Get vector plan", input_model=VectorPlanInput, output_schema=OBJECT_SCHEMA, tags=["vector"])
async def get_vector_plan(ctx: AgentActionContext, payload: VectorPlanInput) -> Any:
    """Get vectorization plan.

    Use after a chunk run completes to inspect files, chunk counts and vector database options. batch_id and chunk_run_id are required and must belong together. Returns file summaries and available vector database adapters. Fails if chunk run is not completed.
    """
    return await vectors.get_vector_plan(ctx.session, payload.batch_id, payload.chunk_run_id)


@smartrag_action(name="create_vector_run", title="Create vector run", input_model=CreateVectorRunInput, output_schema=OBJECT_SCHEMA, permission_scope="vector:write", tags=["vector"])
async def create_vector_run(ctx: AgentActionContext, payload: CreateVectorRunInput) -> dict[str, Any]:
    """Create and start a vectorization run.

    Use after get_vector_plan when embedding model and vector database config are known. Returns run_id and scheduling status for a background vector task. Fails if chunk run is incomplete, embedding model is invalid, or vector database config is invalid.
    """
    run = await vectors.create_vector_run(ctx.session, payload)
    asyncio.create_task(vectors.execute_vector_run(run.run_id))
    return _started(run.run_id, "vector")


@smartrag_action(name="list_vector_runs", title="List vector runs", output_schema=LIST_SCHEMA, tags=["vector"])
async def list_vector_runs(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """List vectorization runs.

    Use to inspect vector indexes and choose a completed vector_run_id for RAG flow creation. Returns run ids, status counters, vector stats, collection metadata and timestamps. Fails only when database access fails.
    """
    return await vectors.list_vector_runs(ctx.session)


@smartrag_action(name="get_vector_run", title="Get vector run", input_model=RunIdInput, output_schema=OBJECT_SCHEMA, tags=["vector"], resource_uri_template="smartrag://vector-runs/{run_id}/summary")
async def get_vector_run(ctx: AgentActionContext, payload: RunIdInput) -> Any:
    """Get vector run summary.

    Use to poll vectorization progress or verify collection details before creating RAG flows. run_id is required. Returns vector store, collection, embedding model snapshot, status and stats. Fails if the run does not exist.
    """
    return await vectors.get_vector_run(ctx.session, payload.run_id)


@smartrag_action(name="delete_vector_run", title="Delete vector run", input_model=RunIdInput, output_schema=OBJECT_SCHEMA, permission_scope="vector:delete", is_destructive=True, tags=["vector"])
async def delete_vector_run(ctx: AgentActionContext, payload: RunIdInput) -> dict[str, Any]:
    """Delete a vector run and collection.

    Use only after explicit user intent to remove a vector index. run_id is required. Attempts to delete the underlying vector collection before deleting records. Returns deleted=true and run_id. Fails if collection deletion fails or the run is missing.
    """
    await vectors.delete_vector_run(ctx.session, payload.run_id)
    return {"deleted": True, "run_id": payload.run_id}


@smartrag_action(name="list_vector_file_runs", title="List vector file runs", input_model=RunIdInput, output_schema=LIST_SCHEMA, tags=["vector"])
async def list_vector_file_runs(ctx: AgentActionContext, payload: RunIdInput) -> Any:
    """List per-file vectorization results.

    Use when inspecting vectorization progress or failures by source file. run_id is required. Returns file ids, chunk counts, vector counts, latency and errors. Fails if the vector run does not exist.
    """
    return await vectors.list_vector_file_runs(ctx.session, payload.run_id)


@smartrag_action(name="compare_vector_runs", title="Compare vector runs", input_model=BatchIdInput, output_schema=LIST_SCHEMA, tags=["vector"])
async def compare_vector_runs(ctx: AgentActionContext, payload: BatchIdInput) -> Any:
    """Compare vector runs in a batch.

    Use when selecting a vector index or comparing embedding/vector database configurations. batch_id is required. Returns vector run stats and configuration summaries. Fails if the batch does not exist.
    """
    return await vectors.compare_batch_vector_runs(ctx.session, payload.batch_id)


@smartrag_action(name="list_rag_components", title="List RAG components", input_model=RagComponentInput, output_schema=LIST_SCHEMA, tags=["rag"])
async def list_rag_components(ctx: AgentActionContext, payload: RagComponentInput) -> Any:
    """List RAG component types.

    Use before creating component configs or RAG flows. Optional node_type filters components. Returns module types, schemas, requirements, LLM/embedding needs and availability. Fails only when registry inspection fails.
    """
    return await rag.list_rag_components(payload.node_type)


@smartrag_action(name="list_component_configs", title="List component configs", input_model=ListComponentConfigsInput, output_schema=LIST_SCHEMA, tags=["rag"])
async def list_component_configs(ctx: AgentActionContext, payload: ListComponentConfigsInput) -> Any:
    """List reusable RAG component configs.

    Use before building or validating a RAG flow. Optional node_type filters configs. Returns config ids, display names, masked secret status, enabled flags and availability. Fails only when database access fails.
    """
    return await rag.list_component_configs(ctx.session, payload.node_type)


@smartrag_action(name="create_component_config", title="Create component config", input_model=CreateComponentConfigInput, output_schema=OBJECT_SCHEMA, permission_scope="rag:write", tags=["rag"])
async def create_component_config(ctx: AgentActionContext, payload: CreateComponentConfigInput) -> Any:
    """Create a reusable RAG component config.

    Use when a reranker, filter or compressor requires shared configuration. node_type/module_type must be known and config must satisfy schema requirements. Returns created config metadata with secrets masked. Fails on unknown components or missing required config.
    """
    return await rag.create_component_config(ctx.session, payload)


@smartrag_action(name="update_component_config", title="Update component config", input_model=UpdateComponentConfigInput, output_schema=OBJECT_SCHEMA, permission_scope="rag:write", is_destructive=True, tags=["rag"])
async def update_component_config(ctx: AgentActionContext, payload: UpdateComponentConfigInput) -> Any:
    """Update a reusable RAG component config.

    Use only when the user asks to change an existing component configuration. config_id is required and updates must satisfy component schema. Returns updated config metadata with secrets masked. Fails if config is missing or invalid.
    """
    data = payload.model_dump(exclude_unset=True)
    config_id = data.pop("config_id")
    return await rag.update_component_config(ctx.session, config_id, ComponentConfigUpdate.model_validate(data))


@smartrag_action(name="delete_component_config", title="Delete component config", input_model=ConfigIdInput, output_schema=OBJECT_SCHEMA, permission_scope="rag:delete", is_destructive=True, tags=["rag"])
async def delete_component_config(ctx: AgentActionContext, payload: ConfigIdInput) -> dict[str, Any]:
    """Delete a reusable RAG component config.

    Use only after explicit user intent to remove a component configuration. config_id is required. Returns deleted=true and config_id. Fails if the config does not exist.
    """
    await rag.delete_component_config(ctx.session, payload.config_id)
    return {"deleted": True, "config_id": payload.config_id}


@smartrag_action(name="list_rag_flows", title="List RAG flows", output_schema=LIST_SCHEMA, tags=["rag"])
async def list_rag_flows(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """List RAG flows.

    Use to inspect configured retrieval/answer pipelines and select a flow_id for query execution or evaluation. Returns flow ids, names, vector run linkage, nodes and enabled status. Fails only when database access fails.
    """
    return await rag.list_rag_flows(ctx.session)


@smartrag_action(name="create_rag_flow", title="Create RAG flow", input_model=CreateRagFlowInput, output_schema=OBJECT_SCHEMA, permission_scope="rag:write", tags=["rag"])
async def create_rag_flow(ctx: AgentActionContext, payload: CreateRagFlowInput) -> Any:
    """Create a RAG flow.

    Use when a completed vector_run_id and node plan are known. Flow must include exactly one enabled retrieval node and valid component configs. Returns created flow metadata. Fails if vector run is incomplete or node configs are invalid.
    """
    return await rag.create_rag_flow(ctx.session, payload)


@smartrag_action(name="get_rag_flow", title="Get RAG flow", input_model=FlowIdInput, output_schema=OBJECT_SCHEMA, tags=["rag"])
async def get_rag_flow(ctx: AgentActionContext, payload: FlowIdInput) -> Any:
    """Get one RAG flow.

    Use when the agent needs exact flow nodes, retrieval config, vector linkage or enabled status. flow_id is required. Returns full flow metadata. Fails if the flow does not exist.
    """
    return await rag.get_rag_flow(ctx.session, payload.flow_id)


@smartrag_action(name="update_rag_flow", title="Update RAG flow", input_model=UpdateRagFlowInput, output_schema=OBJECT_SCHEMA, permission_scope="rag:write", is_destructive=True, tags=["rag"])
async def update_rag_flow(ctx: AgentActionContext, payload: UpdateRagFlowInput) -> Any:
    """Update a RAG flow.

    Use only when the user asks to edit an existing flow. flow_id is required; changed vector_run_id or nodes will be revalidated. Returns updated flow metadata. Fails if the flow is missing or invalid.
    """
    data = payload.model_dump(exclude_unset=True)
    flow_id = data.pop("flow_id")
    return await rag.update_rag_flow(ctx.session, flow_id, RagFlowUpdate.model_validate(data))


@smartrag_action(name="delete_rag_flow", title="Delete RAG flow", input_model=FlowIdInput, output_schema=OBJECT_SCHEMA, permission_scope="rag:delete", is_destructive=True, tags=["rag"])
async def delete_rag_flow(ctx: AgentActionContext, payload: FlowIdInput) -> dict[str, Any]:
    """Delete a RAG flow.

    Use only after explicit user intent to remove a flow. flow_id is required. Returns deleted=true and flow_id. Fails if the flow does not exist or is protected by dependencies.
    """
    await rag.delete_rag_flow(ctx.session, payload.flow_id)
    return {"deleted": True, "flow_id": payload.flow_id}


@smartrag_action(name="run_rag_flow", title="Run RAG flow", input_model=RunRagFlowInput, output_schema=OBJECT_SCHEMA, permission_scope="rag:run", tags=["rag"])
async def run_rag_flow(ctx: AgentActionContext, payload: RunRagFlowInput) -> Any:
    """Run a RAG flow once.

    Use when the user asks a question against a configured RAG flow. flow_id and query are required. Returns run_id, answer, final passages, trace events, latency and status. Fails when the flow is disabled or retrieval/answer generation fails.
    """
    return await rag.run_rag_flow(ctx.session, payload.flow_id, RagFlowRunCreate(query=payload.query))


@smartrag_action(name="get_rag_flow_run", title="Get RAG flow run", input_model=RunIdInput, output_schema=OBJECT_SCHEMA, tags=["rag"], resource_uri_template="smartrag://rag-flow-runs/{run_id}/trace")
async def get_rag_flow_run(ctx: AgentActionContext, payload: RunIdInput) -> Any:
    """Get a RAG flow run trace and passages.

    Use to inspect a prior RAG execution, including trace events and retrieved passages. run_id is required. Returns answer, final_passages, trace_events, status and latency. Fails if the run does not exist.
    """
    return await rag.get_rag_flow_run(ctx.session, payload.run_id)


@smartrag_action(name="list_parse_evaluators", title="List parse evaluators", output_schema=LIST_SCHEMA, tags=["evaluation"])
async def list_parse_evaluators(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """List parse quality evaluators.

    Use before attempting parse quality evaluation. Returns evaluator metadata, config schema and availability. Fails only when registry inspection fails.
    """
    return await evaluations.list_parse_evaluators()


@smartrag_action(name="create_parse_evaluation_run", title="Create parse evaluation run", input_model=ParseEvaluationInput, output_schema=OBJECT_SCHEMA, permission_scope="evaluation:write", tags=["evaluation"])
async def create_parse_evaluation_run(ctx: AgentActionContext, payload: ParseEvaluationInput) -> dict[str, Any]:
    """Create a parse evaluation run.

    Use when evaluating parse quality for a batch or parse run. This first version validates evaluator selection and may return not implemented if execution is not wired. Returns status metadata when accepted. Fails on unknown evaluator or unavailable execution backend.
    """
    await evaluations.create_parse_evaluation_run(payload)
    return {"accepted": True}


@smartrag_action(name="list_evaluation_frameworks", title="List evaluation frameworks", output_schema=LIST_SCHEMA, tags=["evaluation"])
async def list_evaluation_frameworks(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """List RAG evaluation frameworks.

    Use before creating datasets or reports to choose framework_id and metrics. Returns framework metadata, generator config schema, default metrics and availability. Fails only when registry inspection fails.
    """
    return await evaluations.list_evaluation_frameworks()


@smartrag_action(name="create_evaluation_dataset_run", title="Create evaluation dataset run", input_model=CreateEvaluationDatasetRunInput, output_schema=OBJECT_SCHEMA, permission_scope="evaluation:write", tags=["evaluation"])
async def create_evaluation_dataset_run(ctx: AgentActionContext, payload: CreateEvaluationDatasetRunInput) -> dict[str, Any]:
    """Create and start an evaluation dataset generation run.

    Use after a completed chunk_run_id is known and a judge LLM/embedding model is configured. Returns run_id and scheduling status for background dataset generation. Fails if framework unavailable, chunk run incomplete, or model config invalid.
    """
    run = await evaluations.create_evaluation_dataset_run(ctx.session, payload)
    asyncio.create_task(evaluations.execute_evaluation_dataset_run(run.run_id))
    return _started(run.run_id, "evaluation dataset")


@smartrag_action(name="list_evaluation_dataset_runs", title="List evaluation dataset runs", output_schema=LIST_SCHEMA, tags=["evaluation"])
async def list_evaluation_dataset_runs(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """List evaluation dataset runs.

    Use to inspect generated datasets and choose dataset_run_id for report evaluation. Returns dataset run ids, status, framework, item counts and model linkage. Fails only when database access fails.
    """
    return await evaluations.list_evaluation_dataset_runs(ctx.session)


@smartrag_action(name="get_evaluation_dataset_run", title="Get evaluation dataset run", input_model=RunIdInput, output_schema=OBJECT_SCHEMA, tags=["evaluation"])
async def get_evaluation_dataset_run(ctx: AgentActionContext, payload: RunIdInput) -> Any:
    """Get evaluation dataset run summary.

    Use to poll dataset generation or inspect generated item counts. run_id is required. Returns status, stats, framework, chunk linkage and errors. Fails if the run does not exist.
    """
    return await evaluations.get_evaluation_dataset_run(ctx.session, payload.run_id)


@smartrag_action(name="delete_evaluation_dataset_run", title="Delete evaluation dataset run", input_model=RunIdInput, output_schema=OBJECT_SCHEMA, permission_scope="evaluation:delete", is_destructive=True, tags=["evaluation"])
async def delete_evaluation_dataset_run(ctx: AgentActionContext, payload: RunIdInput) -> dict[str, Any]:
    """Delete an evaluation dataset run.

    Use only after explicit user intent to remove a dataset and owned report/RAG run links. run_id is required. Returns deleted=true and run_id. Fails if the dataset run is still pending or running.
    """
    await evaluations.delete_evaluation_dataset_run(ctx.session, payload.run_id)
    return {"deleted": True, "run_id": payload.run_id}


@smartrag_action(name="list_evaluation_dataset_items", title="List evaluation dataset items", input_model=DatasetItemPageInput, output_schema=OBJECT_SCHEMA, tags=["evaluation"])
async def list_evaluation_dataset_items(ctx: AgentActionContext, payload: DatasetItemPageInput) -> Any:
    """List items in an evaluation dataset.

    Use to inspect generated or manually curated questions and ground truths. run_id is required; offset and limit control pagination. Returns items and page metadata. Fails if the dataset run does not exist.
    """
    return await evaluations.list_evaluation_dataset_items(ctx.session, payload.run_id, payload.offset, payload.limit)


@smartrag_action(name="create_evaluation_dataset_item", title="Create evaluation dataset item", input_model=CreateEvaluationDatasetItemInput, output_schema=OBJECT_SCHEMA, permission_scope="evaluation:write", tags=["evaluation"])
async def create_evaluation_dataset_item(ctx: AgentActionContext, payload: CreateEvaluationDatasetItemInput) -> Any:
    """Create a manual evaluation dataset item.

    Use when the user supplies a question, ground truth and optional reference contexts. run_id is required and the dataset must be editable. Returns created item metadata. Fails if the dataset is running or referenced by active reports.
    """
    data = payload.model_dump()
    run_id = data.pop("run_id")
    return await evaluations.create_evaluation_dataset_item(ctx.session, run_id, EvaluationDatasetItemCreate.model_validate(data))


@smartrag_action(name="update_evaluation_dataset_item", title="Update evaluation dataset item", input_model=UpdateEvaluationDatasetItemInput, output_schema=OBJECT_SCHEMA, permission_scope="evaluation:write", is_destructive=True, tags=["evaluation"])
async def update_evaluation_dataset_item(ctx: AgentActionContext, payload: UpdateEvaluationDatasetItemInput) -> Any:
    """Update an evaluation dataset item.

    Use only when the user asks to edit a specific dataset item. run_id and item_id are required and the dataset must be editable. Returns updated item metadata. Fails if item is missing, dataset is running, or active reports reference the dataset.
    """
    data = payload.model_dump(exclude_unset=True)
    run_id = data.pop("run_id")
    item_id = data.pop("item_id")
    return await evaluations.update_evaluation_dataset_item(ctx.session, run_id, item_id, EvaluationDatasetItemUpdate.model_validate(data))


@smartrag_action(name="delete_evaluation_dataset_item", title="Delete evaluation dataset item", input_model=DatasetItemInput, output_schema=OBJECT_SCHEMA, permission_scope="evaluation:delete", is_destructive=True, tags=["evaluation"])
async def delete_evaluation_dataset_item(ctx: AgentActionContext, payload: DatasetItemInput) -> dict[str, Any]:
    """Delete an evaluation dataset item.

    Use only after explicit user intent to remove one dataset item. run_id and item_id are required. Returns deleted=true and item_id. Fails if reports reference the item or the dataset is not editable.
    """
    await evaluations.delete_evaluation_dataset_item(ctx.session, payload.run_id, payload.item_id)
    return {"deleted": True, "run_id": payload.run_id, "item_id": payload.item_id}


@smartrag_action(name="create_evaluation_report_run", title="Create evaluation report run", input_model=CreateEvaluationReportRunInput, output_schema=OBJECT_SCHEMA, permission_scope="evaluation:write", tags=["evaluation"])
async def create_evaluation_report_run(ctx: AgentActionContext, payload: CreateEvaluationReportRunInput) -> dict[str, Any]:
    """Create and start an evaluation report run.

    Use after a completed dataset_run_id and compatible RAG flow are known. Returns run_id and scheduling status for background report evaluation. Fails if the dataset is incomplete, flow is incompatible, framework unavailable, or required answer generator is missing.
    """
    run = await evaluations.create_evaluation_report_run(ctx.session, payload)
    asyncio.create_task(evaluations.execute_evaluation_report_run(run.run_id))
    return _started(run.run_id, "evaluation report")


@smartrag_action(name="list_evaluation_report_runs", title="List evaluation report runs", output_schema=LIST_SCHEMA, tags=["evaluation"])
async def list_evaluation_report_runs(ctx: AgentActionContext, payload: EmptyActionInput) -> Any:
    """List evaluation report runs.

    Use to inspect application-level RAG evaluation tasks and choose a report run for details or failures. Returns report ids, flow/dataset linkage, metrics, aggregate scores and status counters. Fails only when database access fails.
    """
    return await evaluations.list_evaluation_report_runs(ctx.session)


@smartrag_action(name="get_evaluation_report_run", title="Get evaluation report run", input_model=RunIdInput, output_schema=OBJECT_SCHEMA, tags=["evaluation"])
async def get_evaluation_report_run(ctx: AgentActionContext, payload: RunIdInput) -> Any:
    """Get evaluation report run summary.

    Use to poll report progress or inspect aggregate scores. run_id is required. Returns status, item counters, metrics, aggregate scores and errors. Fails if the report run does not exist.
    """
    return await evaluations.get_evaluation_report_run(ctx.session, payload.run_id)


@smartrag_action(name="delete_evaluation_report_run", title="Delete evaluation report run", input_model=RunIdInput, output_schema=OBJECT_SCHEMA, permission_scope="evaluation:delete", is_destructive=True, tags=["evaluation"])
async def delete_evaluation_report_run(ctx: AgentActionContext, payload: RunIdInput) -> dict[str, Any]:
    """Delete an evaluation report run.

    Use only after explicit user intent to remove a report and owned RAG run links. run_id is required. Returns deleted=true and run_id. Fails if the report is pending or running.
    """
    await evaluations.delete_evaluation_report_run(ctx.session, payload.run_id)
    return {"deleted": True, "run_id": payload.run_id}


@smartrag_action(name="list_evaluation_report_items", title="List evaluation report items", input_model=DatasetItemPageInput, output_schema=OBJECT_SCHEMA, tags=["evaluation"], resource_uri_template="smartrag://evaluation-report-runs/{run_id}/items")
async def list_evaluation_report_items(ctx: AgentActionContext, payload: DatasetItemPageInput) -> Any:
    """List per-question evaluation report items.

    Use to inspect answers, contexts, metric scores, trace events and item-level errors. run_id is required; offset and limit control pagination. Returns report items and page metadata. Fails if the report run does not exist.
    """
    return await evaluations.list_evaluation_report_items(ctx.session, payload.run_id, payload.offset, payload.limit)


@smartrag_action(name="get_evaluation_failure_cases", title="Get evaluation failure cases", input_model=FailureCasesInput, output_schema=LIST_SCHEMA, tags=["evaluation"], resource_uri_template="smartrag://evaluation-report-runs/{report_run_id}/failures")
async def get_evaluation_failure_cases(ctx: AgentActionContext, payload: FailureCasesInput) -> list[dict[str, Any]]:
    """Get failed or suspicious evaluation cases.

    Use after an evaluation report finishes to inspect items with explicit errors or low metric scores. report_run_id is required and limit caps the returned cases. Returns question, answer, contexts, scores, trace events and error. Fails only when database access fails.
    """
    rows = (
        await ctx.session.scalars(
            select(EvaluationReportItem)
            .where(EvaluationReportItem.run_id == payload.report_run_id)
            .order_by(EvaluationReportItem.created_at)
            .limit(payload.limit)
        )
    ).all()
    failures = []
    for row in rows:
        scores = row.scores or {}
        numeric_scores = [float(value) for value in scores.values() if isinstance(value, int | float)]
        low_score = bool(numeric_scores and min(numeric_scores) < 0.5)
        if row.error or low_score:
            failures.append(
                {
                    "item_id": row.item_id,
                    "question": row.question,
                    "answer": row.answer,
                    "contexts": row.contexts,
                    "retrieved_chunk_ids": row.retrieved_chunk_ids,
                    "scores": scores,
                    "trace_events": row.trace_events,
                    "error": row.error,
                }
            )
    if not failures:
        failed_count = await ctx.session.scalar(
            select(func.count()).select_from(EvaluationReportItem).where(
                EvaluationReportItem.run_id == payload.report_run_id,
                EvaluationReportItem.error.is_not(None),
            )
        )
        return [{"report_run_id": payload.report_run_id, "failure_count": int(failed_count or 0), "items": []}]
    return failures
