import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type {
  AgentProfile,
  AgentTypeInfo,
  HealthCheckResult,
  MaterialBatch,
  MaterialBatchVersion,
  MaterialFile,
  ModelConnection,
  ParseFileRun,
  ParseFileRunDetail,
  ParsePlan,
  ParseRun,
  ParserStrategy,
  ProcessingDefaultRule,
  ProviderInfo,
  UploadFilesResult,
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
