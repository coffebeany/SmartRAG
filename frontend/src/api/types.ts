export type ModelCategory = 'llm' | 'embedding' | 'reranker' | 'multimodal' | 'reasoning' | 'moe' | 'vision_embedding' | 'speech' | 'custom'
export type Provider = 'openai_compatible' | 'ollama' | 'custom'

export interface ModelConnection {
  model_id: string
  project_id?: string | null
  display_name: string
  model_category: ModelCategory
  provider: Provider
  base_url: string
  model_name: string
  api_key_masked?: string | null
  api_version?: string | null
  timeout_seconds: number
  max_retries: number
  enabled: boolean
  connection_status: 'unknown' | 'checking' | 'available' | 'failed'
  last_check_at?: string | null
  last_error?: string | null
  resolved_model_name?: string | null
  context_window?: number | null
  max_output_tokens?: number | null
  embedding_dimension?: number | null
  supports_streaming?: boolean | null
  supports_json_schema?: boolean | null
  supports_tools?: boolean | null
  supports_vision?: boolean | null
  supports_batch?: boolean | null
  model_traits: string[]
  pricing?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ProviderInfo {
  provider: Provider
  display_name: string
  default_base_url: string
  supports_categories: ModelCategory[]
}

export interface HealthCheckResult {
  status: 'unknown' | 'checking' | 'available' | 'failed'
  latency_ms?: number | null
  error?: string | null
  response_metadata: Record<string, unknown>
}

export interface AgentTypeInfo {
  agent_type: string
  display_name: string
  default_prompt: string
  output_schema: Record<string, unknown>
}

export interface AgentProfile {
  agent_id: string
  project_id?: string | null
  agent_name: string
  agent_type: string
  model_id: string
  prompt_template: string
  output_schema: Record<string, unknown>
  runtime_config: Record<string, unknown>
  dry_run_status: string
  dry_run_error?: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface MaterialBatch {
  batch_id: string
  project_id?: string | null
  batch_name: string
  description?: string | null
  current_version_id?: string | null
  current_version: number
  file_count: number
  created_by?: string | null
  created_at: string
  updated_at: string
}

export interface MaterialFile {
  file_id: string
  batch_id: string
  original_filename: string
  file_ext: string
  mime_type?: string | null
  size_bytes: number
  checksum: string
  storage_uri: string
  status: 'active' | 'removed'
  created_at: string
  removed_at?: string | null
}

export interface MaterialBatchVersion {
  batch_version_id: string
  batch_id: string
  version_number: number
  parent_version_id?: string | null
  change_type: string
  added_file_ids: string[]
  removed_file_ids: string[]
  active_file_ids_snapshot: string[]
  manifest_uri?: string | null
  created_by?: string | null
  created_at: string
}

export interface UploadFilesResult {
  batch: MaterialBatch
  files: MaterialFile[]
  version: MaterialBatchVersion
  duplicate_checksums: string[]
}

export interface ProcessingDefaultRule {
  rule_id: string
  project_id?: string | null
  file_ext: string
  parser_name: string
  parser_config_yaml?: string | null
  chunker_plugin_id?: string | null
  metadata_strategy_id?: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface ParserStrategy {
  parser_name: string
  display_name: string
  description: string
  supported_file_exts: string[]
  capabilities: string[]
  config_schema: Record<string, unknown>
  default_config: Record<string, unknown>
  source: string
  enabled: boolean
  loaded_at: string
  availability_status: string
  availability_reason: string
  required_dependencies: string[]
  required_env_vars: string[]
  requires_config: boolean
  autorag_module_type?: string | null
  autorag_parse_method?: string | null
}

export interface ParseEvaluator {
  evaluator_name: string
  display_name: string
  description: string
  capabilities: string[]
  config_schema: Record<string, unknown>
  default_config: Record<string, unknown>
  source: string
  enabled: boolean
  availability_status: string
  availability_reason: string
}

export interface ParseEvaluationRunCreate {
  batch_id: string
  parse_run_id?: string | null
  evaluator_name: string
  evaluator_config: Record<string, unknown>
}

export interface ParsePlanFile {
  file: MaterialFile
  default_parser_name?: string | null
  default_parser_config: Record<string, unknown>
  parser_options: ParserStrategy[]
}

export interface ParsePlan {
  batch: MaterialBatch
  files: ParsePlanFile[]
}

export interface ParseRun {
  run_id: string
  batch_id: string
  batch_version_id?: string | null
  status: string
  total_files: number
  completed_files: number
  failed_files: number
  error_summary?: string | null
  started_at?: string | null
  ended_at?: string | null
  created_at: string
  updated_at: string
  batch_name?: string | null
}

export interface ParseFileRun {
  file_run_id: string
  run_id: string
  file_id: string
  parser_name: string
  parser_config: Record<string, unknown>
  status: string
  latency_ms?: number | null
  quality_score?: number | null
  error?: string | null
  output_artifact_uri?: string | null
  started_at?: string | null
  ended_at?: string | null
  created_at: string
  updated_at: string
  original_filename?: string | null
  file_ext?: string | null
}

export interface ParsedDocument {
  parsed_document_id: string
  run_id: string
  file_run_id: string
  file_id: string
  parser_name: string
  text_content: string
  elements: Record<string, unknown>[]
  document_metadata: Record<string, unknown>
  pages: number
  char_count: number
  artifact_uri?: string | null
  created_at: string
}

export interface ParseFileRunDetail {
  file_run: ParseFileRun
  parsed_document?: ParsedDocument | null
}

export interface ParseElementsPage {
  items: Record<string, unknown>[]
  total: number
  offset: number
  limit: number
}

export interface ChunkStrategy {
  chunker_name: string
  display_name: string
  description: string
  module_type: string
  chunk_method: string
  capabilities: string[]
  config_schema: Record<string, unknown>
  default_config: Record<string, unknown>
  source: string
  enabled: boolean
  availability_status: string
  availability_reason: string
  required_dependencies: string[]
  requires_embedding_model: boolean
}

export interface ChunkPlanFile {
  parsed_document_id: string
  file_id: string
  original_filename?: string | null
  parser_name: string
  char_count: number
  pages: number
}

export interface ChunkPlan {
  batch: MaterialBatch
  parse_run: ParseRun
  files: ChunkPlanFile[]
  chunk_options: ChunkStrategy[]
}

export interface ChunkRun {
  run_id: string
  batch_id: string
  batch_version_id?: string | null
  parse_run_id: string
  chunker_name: string
  chunker_config: Record<string, unknown>
  status: string
  total_files: number
  completed_files: number
  failed_files: number
  total_chunks: number
  stats: Record<string, unknown>
  artifact_uri?: string | null
  error_summary?: string | null
  started_at?: string | null
  ended_at?: string | null
  created_at: string
  updated_at: string
  batch_name?: string | null
  parse_status?: string | null
}

export interface ChunkFileRun {
  file_run_id: string
  run_id: string
  parsed_document_id: string
  source_file_id: string
  status: string
  chunk_count: number
  latency_ms?: number | null
  error?: string | null
  artifact_uri?: string | null
  started_at?: string | null
  ended_at?: string | null
  created_at: string
  updated_at: string
  original_filename?: string | null
  parser_name?: string | null
}

export interface Chunk {
  chunk_id: string
  run_id: string
  file_run_id: string
  parsed_document_id: string
  source_file_id: string
  chunk_index: number
  contents: string
  source_text: string
  start_char: number
  end_char: number
  char_count: number
  token_count: number
  chunk_metadata: Record<string, unknown>
  source_element_refs: Record<string, unknown>[]
  strategy_metadata: Record<string, unknown>
  created_at: string
}

export interface ChunkPage {
  items: Chunk[]
  total: number
  offset: number
  limit: number
}

export interface ChunkRunCompare {
  run_id: string
  batch_id: string
  batch_name?: string | null
  parse_run_id: string
  chunker_name: string
  status: string
  total_files: number
  completed_files: number
  failed_files: number
  total_chunks: number
  stats: Record<string, unknown>
  chunker_config: Record<string, unknown>
  started_at?: string | null
  ended_at?: string | null
  created_at: string
}
