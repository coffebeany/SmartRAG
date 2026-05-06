import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type {
  AgentProfile,
  AgentActionSpec,
  AgentTypeInfo,
  LangfuseConfig,
  RagFlowRunSummary,
  ChunkFileRun,
  ChunkPage,
  ChunkPlan,
  ChunkRun,
  ChunkRunCompare,
  ChunkStrategy,
  ComponentConfig,
  EvaluationDatasetItemsPage,
  EvaluationDatasetRun,
  EvaluationFramework,
  EvaluationReportItemsPage,
  EvaluationReportRun,
  HealthCheckResult,
  MaterialBatch,
  MaterialBatchVersion,
  MaterialFile,
  ModelConnection,
  ParseElementsPage,
  ParseEvaluationRunCreate,
  ParseEvaluator,
  ParseFileRun,
  ParseFileRunDetail,
  ParsePlan,
  ParseRun,
  ParserStrategy,
  ProcessingDefaultRule,
  ProviderInfo,
  RagComponent,
  RagFlow,
  RagFlowRun,
  SmartRagAgentRun,
  UploadFilesResult,
  VectorDB,
  VectorFileRun,
  VectorPlan,
  VectorRun,
  VectorRunCompare,
} from './types'

export function useModels() {
  return useQuery({ queryKey: ['models'], queryFn: () => apiClient.get<ModelConnection[]>('/models') })
}

export function useProviders() {
  return useQuery({ queryKey: ['providers'], queryFn: () => apiClient.get<ProviderInfo[]>('/providers') })
}

export function useAgentTypes() {
  return useQuery({ queryKey: ['agent-types'], queryFn: () => apiClient.get<AgentTypeInfo[]>('/agent-types') })
}

export function useAgentActions() {
  return useQuery({ queryKey: ['agent-actions'], queryFn: () => apiClient.get<AgentActionSpec[]>('/agent-actions') })
}

export function useCreateSmartRagAgentRun() {
  return useMutation({
    mutationFn: (payload: { model_id: string; message: string; enabled_action_names?: string[] }) =>
      apiClient.post<SmartRagAgentRun>('/smartrag-agent/runs', payload),
  })
}

export function useSmartRagAgentRun(runId?: string) {
  return useQuery({
    queryKey: ['smartrag-agent-run', runId],
    queryFn: () => apiClient.get<SmartRagAgentRun>(`/smartrag-agent/runs/${runId}`),
    enabled: Boolean(runId),
    refetchOnWindowFocus: false,
  })
}

export function useCancelSmartRagAgentRun() {
  return useMutation({
    mutationFn: (runId: string) => apiClient.post<SmartRagAgentRun>(`/smartrag-agent/runs/${runId}/cancel`),
  })
}

export function useCreateModel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: unknown) => apiClient.post<ModelConnection>('/models', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['models'] }),
  })
}

export function useUpdateModel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ modelId, payload }: { modelId: string; payload: unknown }) => apiClient.patch<ModelConnection>(`/models/${modelId}`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['models'] }),
  })
}

export function useTestModelDraft() {
  return useMutation({
    mutationFn: (payload: unknown) => apiClient.post<HealthCheckResult>('/models/test-connection', payload),
  })
}

export function useTestModelDraftUpdate() {
  return useMutation({
    mutationFn: ({ modelId, payload }: { modelId: string; payload: unknown }) =>
      apiClient.post<HealthCheckResult>(`/models/${modelId}/test-draft-connection`, payload),
  })
}

export function useTestModel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (modelId: string) => apiClient.post(`/models/${modelId}/test-connection`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['models'] }),
  })
}

export function useAgents() {
  return useQuery({ queryKey: ['agents'], queryFn: () => apiClient.get<AgentProfile[]>('/agent-profiles') })
}

export function useCreateAgent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: unknown) => apiClient.post<AgentProfile>('/agent-profiles', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agents'] }),
  })
}

export function useUpdateAgent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ agentId, payload }: { agentId: string; payload: unknown }) => apiClient.patch<AgentProfile>(`/agent-profiles/${agentId}`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agents'] }),
  })
}

export function useDryRunAgent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ agentId, payload }: { agentId: string; payload: unknown }) => apiClient.post(`/agent-profiles/${agentId}/dry-run`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agents'] }),
  })
}

export function useDryRunAgentDraft() {
  return useMutation({
    mutationFn: (payload: unknown) => apiClient.post('/agent-profiles/dry-run', payload),
  })
}

export function useModelDefaults() {
  return useQuery({ queryKey: ['model-defaults'], queryFn: () => apiClient.get<{ defaults: Record<string, string | null> }>('/model-defaults') })
}

export function useUpdateModelDefaults() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { defaults: Record<string, string | null> }) => apiClient.patch('/model-defaults', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['model-defaults'] }),
  })
}

export function useMaterialBatches() {
  return useQuery({
    queryKey: ['material-batches'],
    queryFn: () => apiClient.get<MaterialBatch[]>('/material-batches'),
  })
}

export function useMaterialBatch(batchId?: string) {
  return useQuery({
    queryKey: ['material-batch', batchId],
    queryFn: () => apiClient.get<MaterialBatch>(`/material-batches/${batchId}`),
    enabled: Boolean(batchId),
  })
}

export function useCreateMaterialBatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: unknown) => apiClient.post<MaterialBatch>('/material-batches', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['material-batches'] }),
  })
}

export function useUpdateMaterialBatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ batchId, payload }: { batchId: string; payload: unknown }) =>
      apiClient.patch<MaterialBatch>(`/material-batches/${batchId}`, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['material-batches'] })
      queryClient.invalidateQueries({ queryKey: ['material-batch', variables.batchId] })
    },
  })
}

export function useDeleteMaterialBatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (batchId: string) => apiClient.delete(`/material-batches/${batchId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['material-batches'] }),
  })
}

export function useMaterialFiles(batchId?: string) {
  return useQuery({
    queryKey: ['material-files', batchId],
    queryFn: () => apiClient.get<MaterialFile[]>(`/material-batches/${batchId}/files`),
    enabled: Boolean(batchId),
  })
}

export function useMaterialVersions(batchId?: string) {
  return useQuery({
    queryKey: ['material-versions', batchId],
    queryFn: () => apiClient.get<MaterialBatchVersion[]>(`/material-batches/${batchId}/versions`),
    enabled: Boolean(batchId),
  })
}

export function useUploadMaterialFiles(batchId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (files: File[]) => {
      const form = new FormData()
      files.forEach((file) => form.append('files', file))
      return apiClient.postForm<UploadFilesResult>(`/material-batches/${batchId}/files`, form)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['material-batches'] })
      queryClient.invalidateQueries({ queryKey: ['material-batch', batchId] })
      queryClient.invalidateQueries({ queryKey: ['material-files', batchId] })
      queryClient.invalidateQueries({ queryKey: ['material-versions', batchId] })
    },
  })
}

export function useRemoveMaterialFile(batchId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (fileId: string) => apiClient.delete<MaterialBatchVersion>(`/material-batches/${batchId}/files/${fileId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['material-batches'] })
      queryClient.invalidateQueries({ queryKey: ['material-batch', batchId] })
      queryClient.invalidateQueries({ queryKey: ['material-files', batchId] })
      queryClient.invalidateQueries({ queryKey: ['material-versions', batchId] })
    },
  })
}

export function useProcessingDefaultRules() {
  return useQuery({
    queryKey: ['processing-default-rules'],
    queryFn: () => apiClient.get<ProcessingDefaultRule[]>('/processing-default-rules'),
  })
}

export function useUpdateProcessingDefaultRules() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { rules: unknown[] }) => apiClient.patch<ProcessingDefaultRule[]>('/processing-default-rules', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['processing-default-rules'] }),
  })
}

export function useParserStrategies() {
  return useQuery({
    queryKey: ['parser-strategies'],
    queryFn: () => apiClient.get<ParserStrategy[]>('/parser-strategies'),
  })
}

export function useRefreshParserStrategies() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiClient.post<ParserStrategy[]>('/parser-strategies/refresh'),
    onSuccess: (data) => {
      queryClient.setQueryData(['parser-strategies'], data)
      queryClient.invalidateQueries({ queryKey: ['parse-plan'] })
    },
  })
}

export function useParseEvaluators() {
  return useQuery({
    queryKey: ['parse-evaluators'],
    queryFn: () => apiClient.get<ParseEvaluator[]>('/parse-evaluators'),
  })
}

export function useCreateParseEvaluationRun() {
  return useMutation({
    mutationFn: (payload: ParseEvaluationRunCreate) => apiClient.post('/parse-evaluation-runs', payload),
  })
}

export function useParsePlan(batchId?: string) {
  return useQuery({
    queryKey: ['parse-plan', batchId],
    queryFn: () => apiClient.get<ParsePlan>(`/material-batches/${batchId}/parse-plan`),
    enabled: Boolean(batchId),
  })
}

export function useCreateParseRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: unknown) => apiClient.post<ParseRun>('/parse-runs', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parse-runs'] })
    },
  })
}

export function useParseRuns() {
  return useQuery({
    queryKey: ['parse-runs'],
    queryFn: () => apiClient.get<ParseRun[]>('/parse-runs'),
    refetchInterval: (query) => {
      const runs = query.state.data as ParseRun[] | undefined
      return runs?.some((run) => ['pending', 'running'].includes(run.status)) ? 1500 : false
    },
  })
}

export function useDeleteParseRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (runId: string) => apiClient.delete(`/parse-runs/${runId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parse-runs'] })
    },
  })
}

export function useParseRun(runId?: string) {
  return useQuery({
    queryKey: ['parse-run', runId],
    queryFn: () => apiClient.get<ParseRun>(`/parse-runs/${runId}`),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const run = query.state.data as ParseRun | undefined
      return run && ['pending', 'running'].includes(run.status) ? 1500 : false
    },
  })
}

export function useParseFileRuns(runId?: string) {
  return useQuery({
    queryKey: ['parse-file-runs', runId],
    queryFn: () => apiClient.get<ParseFileRun[]>(`/parse-runs/${runId}/files`),
    enabled: Boolean(runId),
    refetchInterval: 1500,
  })
}

export function useParseFileRunDetail(runId?: string, fileRunId?: string) {
  return useQuery({
    queryKey: ['parse-file-run-detail', runId, fileRunId],
    queryFn: () => apiClient.get<ParseFileRunDetail>(`/parse-runs/${runId}/files/${fileRunId}`),
    enabled: Boolean(runId && fileRunId),
  })
}

export function useParseFileRunElements(
  runId?: string,
  fileRunId?: string,
  offset = 0,
  limit = 50,
) {
  return useQuery({
    queryKey: ['parse-file-run-elements', runId, fileRunId, offset, limit],
    queryFn: () =>
      apiClient.get<ParseElementsPage>(
        `/parse-runs/${runId}/files/${fileRunId}/elements?offset=${offset}&limit=${limit}`,
      ),
    enabled: Boolean(runId && fileRunId),
  })
}

export function useChunkStrategies() {
  return useQuery({
    queryKey: ['chunk-strategies'],
    queryFn: () => apiClient.get<ChunkStrategy[]>('/chunk-strategies'),
  })
}

export function useRefreshChunkStrategies() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiClient.post<ChunkStrategy[]>('/chunk-strategies/refresh'),
    onSuccess: (data) => {
      queryClient.setQueryData(['chunk-strategies'], data)
      queryClient.invalidateQueries({ queryKey: ['chunk-plan'] })
    },
  })
}

export function useChunkPlan(batchId?: string, parseRunId?: string) {
  return useQuery({
    queryKey: ['chunk-plan', batchId, parseRunId],
    queryFn: () => apiClient.get<ChunkPlan>(`/material-batches/${batchId}/chunk-plan?parse_run_id=${parseRunId}`),
    enabled: Boolean(batchId && parseRunId),
  })
}

export function useCreateChunkRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: unknown) => apiClient.post<ChunkRun>('/chunk-runs', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['chunk-runs'] }),
  })
}

export function useChunkRuns() {
  return useQuery({
    queryKey: ['chunk-runs'],
    queryFn: () => apiClient.get<ChunkRun[]>('/chunk-runs'),
    refetchInterval: (query) => {
      const runs = query.state.data as ChunkRun[] | undefined
      return runs?.some((run) => ['pending', 'running'].includes(run.status)) ? 1500 : false
    },
  })
}

export function useDeleteChunkRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (runId: string) => apiClient.delete(`/chunk-runs/${runId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['chunk-runs'] }),
  })
}

export function useChunkRun(runId?: string) {
  return useQuery({
    queryKey: ['chunk-run', runId],
    queryFn: () => apiClient.get<ChunkRun>(`/chunk-runs/${runId}`),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const run = query.state.data as ChunkRun | undefined
      return run && ['pending', 'running'].includes(run.status) ? 1500 : false
    },
  })
}

export function useChunkFileRuns(runId?: string) {
  return useQuery({
    queryKey: ['chunk-file-runs', runId],
    queryFn: () => apiClient.get<ChunkFileRun[]>(`/chunk-runs/${runId}/files`),
    enabled: Boolean(runId),
    refetchInterval: 1500,
  })
}

export function useChunkFileRunChunks(runId?: string, fileRunId?: string, offset = 0, limit = 50) {
  return useQuery({
    queryKey: ['chunk-file-run-chunks', runId, fileRunId, offset, limit],
    queryFn: () => apiClient.get<ChunkPage>(`/chunk-runs/${runId}/files/${fileRunId}/chunks?offset=${offset}&limit=${limit}`),
    enabled: Boolean(runId && fileRunId),
  })
}

export function useChunkRunCompare(batchId?: string) {
  return useQuery({
    queryKey: ['chunk-run-compare', batchId],
    queryFn: () => apiClient.get<ChunkRunCompare[]>(`/material-batches/${batchId}/chunk-runs/compare`),
    enabled: Boolean(batchId),
  })
}

export function useVectorDBs() {
  return useQuery({
    queryKey: ['vectordbs'],
    queryFn: () => apiClient.get<VectorDB[]>('/vectordbs'),
  })
}

export function useRefreshVectorDBs() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiClient.post<VectorDB[]>('/vectordbs/refresh'),
    onSuccess: (data) => {
      queryClient.setQueryData(['vectordbs'], data)
      queryClient.invalidateQueries({ queryKey: ['vector-plan'] })
    },
  })
}

export function useVectorPlan(batchId?: string, chunkRunId?: string) {
  return useQuery({
    queryKey: ['vector-plan', batchId, chunkRunId],
    queryFn: () => apiClient.get<VectorPlan>(`/material-batches/${batchId}/vector-plan?chunk_run_id=${chunkRunId}`),
    enabled: Boolean(batchId && chunkRunId),
  })
}

export function useCreateVectorRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: unknown) => apiClient.post<VectorRun>('/vector-runs', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['vector-runs'] }),
  })
}

export function useVectorRuns() {
  return useQuery({
    queryKey: ['vector-runs'],
    queryFn: () => apiClient.get<VectorRun[]>('/vector-runs'),
    refetchInterval: (query) => {
      const runs = query.state.data as VectorRun[] | undefined
      return runs?.some((run) => ['pending', 'running'].includes(run.status)) ? 1500 : false
    },
  })
}

export function useDeleteVectorRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (runId: string) => apiClient.delete(`/vector-runs/${runId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['vector-runs'] }),
  })
}

export function useVectorRun(runId?: string) {
  return useQuery({
    queryKey: ['vector-run', runId],
    queryFn: () => apiClient.get<VectorRun>(`/vector-runs/${runId}`),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const run = query.state.data as VectorRun | undefined
      return run && ['pending', 'running'].includes(run.status) ? 1500 : false
    },
  })
}

export function useVectorFileRuns(runId?: string) {
  return useQuery({
    queryKey: ['vector-file-runs', runId],
    queryFn: () => apiClient.get<VectorFileRun[]>(`/vector-runs/${runId}/files`),
    enabled: Boolean(runId),
    refetchInterval: 1500,
  })
}

export function useVectorRunCompare(batchId?: string) {
  return useQuery({
    queryKey: ['vector-run-compare', batchId],
    queryFn: () => apiClient.get<VectorRunCompare[]>(`/material-batches/${batchId}/vector-runs/compare`),
    enabled: Boolean(batchId),
  })
}

export function useRagComponents(nodeType?: string) {
  return useQuery({
    queryKey: ['rag-components', nodeType],
    queryFn: () => apiClient.get<RagComponent[]>(`/rag-components${nodeType ? `?node_type=${nodeType}` : ''}`),
  })
}

export function useComponentConfigs(nodeType?: string) {
  return useQuery({
    queryKey: ['component-configs', nodeType],
    queryFn: () => apiClient.get<ComponentConfig[]>(`/component-configs${nodeType ? `?node_type=${nodeType}` : ''}`),
  })
}

export function useCreateComponentConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: unknown) => apiClient.post<ComponentConfig>('/component-configs', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['component-configs'] }),
  })
}

export function useUpdateComponentConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ configId, payload }: { configId: string; payload: unknown }) =>
      apiClient.patch<ComponentConfig>(`/component-configs/${configId}`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['component-configs'] }),
  })
}

export function useDeleteComponentConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (configId: string) => apiClient.delete(`/component-configs/${configId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['component-configs'] }),
  })
}

export function useRagFlows() {
  return useQuery({
    queryKey: ['rag-flows'],
    queryFn: () => apiClient.get<RagFlow[]>('/rag-flows'),
  })
}

export function useCreateRagFlow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: unknown) => apiClient.post<RagFlow>('/rag-flows', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rag-flows'] }),
  })
}

export function useUpdateRagFlow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ flowId, payload }: { flowId: string; payload: unknown }) =>
      apiClient.patch<RagFlow>(`/rag-flows/${flowId}`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rag-flows'] }),
  })
}

export function useDeleteRagFlow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (flowId: string) => apiClient.delete(`/rag-flows/${flowId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rag-flows'] }),
  })
}

export function useRunRagFlow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ flowId, query }: { flowId: string; query: string }) =>
      apiClient.post<RagFlowRun>(`/rag-flows/${flowId}/run`, { query }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rag-flows'] })
      queryClient.invalidateQueries({ queryKey: ['rag-flow-runs'] })
    },
  })
}

export function useRagFlowRuns(flowId?: string) {
  return useQuery({
    queryKey: ['rag-flow-runs', flowId],
    queryFn: () => {
      const params = new URLSearchParams()
      if (flowId) params.set('flow_id', flowId)
      params.set('limit', '100')
      const qs = params.toString()
      return apiClient.get<RagFlowRunSummary[]>(`/rag-flow-runs${qs ? `?${qs}` : ''}`)
    },
  })
}

export function useDeleteRagFlowRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (runId: string) => apiClient.delete(`/rag-flow-runs/${runId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rag-flow-runs'] }),
  })
}

export function useAgentRuns() {
  return useQuery({
    queryKey: ['agent-runs'],
    queryFn: () => apiClient.get<SmartRagAgentRun[]>('/smartrag-agent/runs?limit=100'),
  })
}

export function useDeleteAgentRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (runId: string) => apiClient.delete(`/smartrag-agent/runs/${runId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agent-runs'] }),
  })
}

export function useEvaluationFrameworks() {
  return useQuery({
    queryKey: ['evaluation-frameworks'],
    queryFn: () => apiClient.get<EvaluationFramework[]>('/evaluation-frameworks'),
  })
}

export function useCreateEvaluationDatasetRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: unknown) => apiClient.post<EvaluationDatasetRun>('/evaluation-dataset-runs', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['evaluation-dataset-runs'] }),
  })
}

export function useEvaluationDatasetRuns() {
  return useQuery({
    queryKey: ['evaluation-dataset-runs'],
    queryFn: () => apiClient.get<EvaluationDatasetRun[]>('/evaluation-dataset-runs'),
    refetchInterval: (query) => {
      const runs = query.state.data as EvaluationDatasetRun[] | undefined
      return runs?.some((run) => ['pending', 'running'].includes(run.status)) ? 1500 : false
    },
  })
}

export function useEvaluationDatasetRun(runId?: string) {
  return useQuery({
    queryKey: ['evaluation-dataset-run', runId],
    queryFn: () => apiClient.get<EvaluationDatasetRun>(`/evaluation-dataset-runs/${runId}`),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const run = query.state.data as EvaluationDatasetRun | undefined
      return run && ['pending', 'running'].includes(run.status) ? 1500 : false
    },
  })
}

export function useDeleteEvaluationDatasetRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (runId: string) => apiClient.delete(`/evaluation-dataset-runs/${runId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evaluation-dataset-runs'] })
      queryClient.invalidateQueries({ queryKey: ['evaluation-report-runs'] })
    },
  })
}

export function useEvaluationDatasetItems(runId?: string, offset = 0, limit = 50) {
  return useQuery({
    queryKey: ['evaluation-dataset-items', runId, offset, limit],
    queryFn: () => apiClient.get<EvaluationDatasetItemsPage>(`/evaluation-dataset-runs/${runId}/items?offset=${offset}&limit=${limit}`),
    enabled: Boolean(runId),
  })
}

function invalidateEvaluationDatasetItemQueries(queryClient: ReturnType<typeof useQueryClient>, runId?: string) {
  queryClient.invalidateQueries({ queryKey: ['evaluation-dataset-runs'] })
  queryClient.invalidateQueries({ queryKey: ['evaluation-dataset-run', runId] })
  queryClient.invalidateQueries({ queryKey: ['evaluation-dataset-items', runId] })
}

export function useCreateEvaluationDatasetItem(runId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: unknown) => apiClient.post(`/evaluation-dataset-runs/${runId}/items`, payload),
    onSuccess: () => invalidateEvaluationDatasetItemQueries(queryClient, runId),
  })
}

export function useUpdateEvaluationDatasetItem(runId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ itemId, payload }: { itemId: string; payload: unknown }) =>
      apiClient.patch(`/evaluation-dataset-runs/${runId}/items/${itemId}`, payload),
    onSuccess: () => invalidateEvaluationDatasetItemQueries(queryClient, runId),
  })
}

export function useDeleteEvaluationDatasetItem(runId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (itemId: string) => apiClient.delete(`/evaluation-dataset-runs/${runId}/items/${itemId}`),
    onSuccess: () => invalidateEvaluationDatasetItemQueries(queryClient, runId),
  })
}

export function useCreateEvaluationReportRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: unknown) => apiClient.post<EvaluationReportRun>('/evaluation-report-runs', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['evaluation-report-runs'] }),
  })
}

export function useBatchCreateEvaluationReportRuns() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: unknown) => apiClient.post<EvaluationReportRun[]>('/evaluation-report-runs/batch', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['evaluation-report-runs'] }),
  })
}

export function useEvaluationReportRuns() {
  return useQuery({
    queryKey: ['evaluation-report-runs'],
    queryFn: () => apiClient.get<EvaluationReportRun[]>('/evaluation-report-runs'),
    refetchInterval: (query) => {
      const runs = query.state.data as EvaluationReportRun[] | undefined
      return runs?.some((run) => ['pending', 'running'].includes(run.status)) ? 1500 : false
    },
  })
}

export function useEvaluationReportRun(runId?: string) {
  return useQuery({
    queryKey: ['evaluation-report-run', runId],
    queryFn: () => apiClient.get<EvaluationReportRun>(`/evaluation-report-runs/${runId}`),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const run = query.state.data as EvaluationReportRun | undefined
      return run && ['pending', 'running'].includes(run.status) ? 1500 : false
    },
  })
}

export function useDeleteEvaluationReportRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (runId: string) => apiClient.delete(`/evaluation-report-runs/${runId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['evaluation-report-runs'] }),
  })
}

export function useEvaluationReportItems(runId?: string, offset = 0, limit = 50) {
  return useQuery({
    queryKey: ['evaluation-report-items', runId, offset, limit],
    queryFn: () => apiClient.get<EvaluationReportItemsPage>(`/evaluation-report-runs/${runId}/items?offset=${offset}&limit=${limit}`),
    enabled: Boolean(runId),
  })
}

export function useLangfuseConfig() {
  return useQuery({
    queryKey: ['langfuse-config'],
    queryFn: () => apiClient.get<LangfuseConfig>('/langfuse-config'),
    staleTime: 5 * 60 * 1000,
  })
}
