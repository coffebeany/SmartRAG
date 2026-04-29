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

export interface RagComponent {
  node_type: string
  module_type: string
  display_name: string
  description: string
  capabilities: string[]
  config_schema: Record<string, unknown>
  secret_config_schema: Record<string, unknown>
  default_config: Record<string, unknown>
  source: string
  executable: boolean
  requires_config: boolean
  required_dependencies: string[]
  required_env_vars: string[]
  requires_llm: boolean
  llm_config_mode: 'none' | 'model_only' | 'agent_profile_required'
  requires_embedding: boolean
  requires_api_key: boolean
  dependency_install_hint?: string | null
  availability_status: string
  availability_reason: string
}

export interface ComponentConfig {
  config_id: string
  node_type: string
  module_type: string
  display_name: string
  config: Record<string, unknown>
  secret_config_masked: Record<string, string | null>
  enabled: boolean
  availability_status: string
  availability_reason: string
  created_at: string
  updated_at: string
}

export interface RagFlowNode {
  node_type: string
  module_type: string
  config: Record<string, unknown>
  component_config_id?: string | null
  enabled: boolean
}

export interface RagFlow {
  flow_id: string
  flow_name: string
  description?: string | null
  vector_run_id: string
  vector_run_status?: string | null
  batch_name?: string | null
  vectordb_name?: string | null
  retrieval_config: Record<string, unknown>
  nodes: RagFlowNode[]
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface RagFlowRun {
  run_id: string
  flow_id: string
  query: string
  status: string
  answer?: string | null
  answer_metadata: Record<string, unknown>
  final_passages: Record<string, unknown>[]
  trace_events: Record<string, unknown>[]
  latency_ms?: number | null
  error?: string | null
  created_at: string
  updated_at: string
}

export interface AgentActionSpec {
  name: string
  title: string
  description: string
  input_schema: Record<string, unknown>
  output_schema: Record<string, unknown>
  permission_scope: string
  is_destructive: boolean
  tags: string[]
  resource_uri_template?: string | null
}

export type AgentRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export type AgentRunEventType =
  | 'message_delta'
  | 'reasoning_delta'
  | 'tool_call_started'
  | 'tool_call_result'
  | 'tool_call_error'
  | 'final_answer'
  | 'run_error'
  | 'run_cancelled'

export interface AgentToolLog {
  tool_log_id: string
  run_id: string
  tool_name: string
  tool_args: Record<string, unknown>
  status: string
  output?: unknown
  error?: string | null
  latency_ms?: number | null
  started_at?: string | null
  ended_at?: string | null
  created_at: string
}

export interface AgentRunEvent {
  event_id: string
  run_id: string
  event_type: AgentRunEventType
  sequence: number
  payload: Record<string, unknown>
  created_at: string
}

export interface SmartRagAgentRun {
  run_id: string
  model_id: string
  message: string
  enabled_action_names: string[]
  status: AgentRunStatus
  answer?: string | null
  error?: string | null
  created_at: string
  updated_at: string
  started_at?: string | null
  ended_at?: string | null
  tool_logs: AgentToolLog[]
  events: AgentRunEvent[]
}

export interface EvaluationMetric {
  metric_id: string
  display_name: string
  description: string
  category: string
  requires_answer: boolean
  requires_ground_truth: boolean
  requires_contexts: boolean
}

export interface EvaluationFramework {
  framework_id: string
  display_name: string
  description: string
  source: string
  default_metrics: string[]
  metrics: EvaluationMetric[]
  generator_config_schema: Record<string, unknown>
  default_generator_config: Record<string, unknown>
  availability_status: string
  availability_reason: string
  dependency_install_hint?: string | null
}

export interface EvaluationDatasetRun {
  run_id: string
  display_name?: string | null
  batch_id: string
  chunk_run_id: string
  framework_id: string
  generator_config: Record<string, unknown>
  judge_llm_model_id?: string | null
  embedding_model_id?: string | null
  status: string
  total_items: number
  completed_items: number
  failed_items: number
  stats: Record<string, unknown>
  error_summary?: string | null
  started_at?: string | null
  ended_at?: string | null
  created_at: string
  updated_at: string
  batch_name?: string | null
  chunk_status?: string | null
}

export interface EvaluationDatasetItem {
  item_id: string
  run_id: string
  question: string
  ground_truth: string
  reference_contexts: string[]
  source_chunk_ids: string[]
  source_file_ids: string[]
  synthesizer_name?: string | null
  item_metadata: Record<string, unknown>
  created_at: string
}

export interface EvaluationDatasetItemsPage {
  items: EvaluationDatasetItem[]
  total: number
  offset: number
  limit: number
}

export interface EvaluationReportRun {
  run_id: string
  flow_id: string
  dataset_run_id: string
  framework_id: string
  metric_ids: string[]
  evaluator_config: Record<string, unknown>
  aggregate_scores: Record<string, number>
  status: string
  total_items: number
  completed_items: number
  failed_items: number
  error_summary?: string | null
  started_at?: string | null
  ended_at?: string | null
  created_at: string
  updated_at: string
  flow_name?: string | null
  dataset_status?: string | null
}

export interface EvaluationReportItem {
  item_id: string
  run_id: string
  dataset_item_id: string
  rag_flow_run_id?: string | null
  question: string
  answer?: string | null
  contexts: string[]
  retrieved_chunk_ids: string[]
  scores: Record<string, number>
  trace_events: Record<string, unknown>[]
  latency_ms?: number | null
  error?: string | null
  created_at: string
}

export interface EvaluationReportItemsPage {
  items: EvaluationReportItem[]
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

export interface VectorDB {
  vectordb_name: string
  display_name: string
  description: string
  db_type: string
  capabilities: string[]
  config_schema: Record<string, unknown>
  default_config: Record<string, unknown>
  advanced_options_schema: Record<string, unknown>
  default_storage_uri?: string | null
  source: string
  enabled: boolean
  availability_status: string
  availability_reason: string
  required_dependencies: string[]
}

export interface VectorPlanFile {
  chunk_file_run_id: string
  source_file_id: string
  original_filename?: string | null
  status: string
  chunk_count: number
  char_count: number
  token_count: number
}

export interface VectorPlan {
  batch: MaterialBatch
  chunk_run: ChunkRun
  files: VectorPlanFile[]
  vectordbs: VectorDB[]
}

export interface VectorRun {
  run_id: string
  batch_id: string
  batch_version_id?: string | null
  chunk_run_id: string
  embedding_model_id: string
  embedding_model_snapshot: Record<string, unknown>
  vectordb_name: string
  vectordb_config: Record<string, unknown>
  embedding_config: Record<string, unknown>
  index_config: Record<string, unknown>
  file_selection: Record<string, unknown>
  collection_name: string
  storage_uri: string
  similarity_metric: string
  embedding_dimension?: number | null
  status: string
  total_files: number
  completed_files: number
  failed_files: number
  total_chunks: number
  total_vectors: number
  stats: Record<string, unknown>
  error_summary?: string | null
  started_at?: string | null
  ended_at?: string | null
  created_at: string
  updated_at: string
  batch_name?: string | null
  chunk_status?: string | null
}

export interface VectorFileRun {
  file_run_id: string
  run_id: string
  chunk_file_run_id: string
  source_file_id: string
  status: string
  chunk_count: number
  vector_count: number
  failed_vectors: number
  latency_ms?: number | null
  error?: string | null
  started_at?: string | null
  ended_at?: string | null
  created_at: string
  updated_at: string
  original_filename?: string | null
}

export interface VectorRunCompare {
  run_id: string
  batch_id: string
  batch_name?: string | null
  chunk_run_id: string
  embedding_model_id: string
  embedding_model_name?: string | null
  vectordb_name: string
  status: string
  total_files: number
  completed_files: number
  failed_files: number
  total_chunks: number
  total_vectors: number
  similarity_metric: string
  embedding_dimension?: number | null
  stats: Record<string, unknown>
  started_at?: string | null
  ended_at?: string | null
  created_at: string
}
