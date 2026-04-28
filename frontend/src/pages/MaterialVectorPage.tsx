import { Alert, App, Button, Card, Checkbox, Form, Input, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useChunkRuns,
  useCreateVectorRun,
  useMaterialBatches,
  useModels,
  useVectorDBs,
  useVectorPlan,
  useVectorRuns,
} from '../api/hooks'
import type { VectorDB, VectorPlanFile } from '../api/types'

const EXECUTABLE_STATUSES = new Set(['available'])

function stringifyConfig(config: Record<string, unknown> | undefined) {
  return JSON.stringify(config ?? {}, null, 2)
}

function statusColor(status?: string) {
  if (status === 'available') return 'green'
  if (status === 'adapter_only') return 'blue'
  if (status === 'needs_config') return 'gold'
  return 'red'
}

function parseJson(text: string) {
  return JSON.parse(text || '{}') as Record<string, unknown>
}

export default function MaterialVectorPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [batchId, setBatchId] = useState<string>()
  const [chunkRunId, setChunkRunId] = useState<string>()
  const [embeddingModelId, setEmbeddingModelId] = useState<string>()
  const [vectordbName, setVectordbName] = useState<string>('chroma')
  const [vectordbConfigText, setVectordbConfigText] = useState('{}')
  const [embeddingConfigText, setEmbeddingConfigText] = useState('{\n  "normalize_embeddings": false,\n  "embedding_batch": 100\n}')
  const [indexConfigText, setIndexConfigText] = useState('{\n  "similarity_metric": "cosine",\n  "metadata_mode": "full"\n}')
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>([])
  const [useTestRelated, setUseTestRelated] = useState(false)

  const batches = useMaterialBatches()
  const chunkRuns = useChunkRuns()
  const models = useModels()
  const vectordbs = useVectorDBs()
  const vectorPlan = useVectorPlan(batchId, chunkRunId)
  const vectorRuns = useVectorRuns()
  const createVectorRun = useCreateVectorRun()

  const chunkRunOptions = (chunkRuns.data ?? [])
    .filter((run) => run.batch_id === batchId && ['completed', 'completed_with_errors'].includes(run.status))
    .map((run) => ({
      value: run.run_id,
      label: `${run.chunker_name} / ${run.status} / ${new Date(run.created_at).toLocaleString()}`,
    }))

  const embeddingOptions = (models.data ?? [])
    .filter((model) => model.model_category === 'embedding' && model.enabled && model.connection_status !== 'failed')
    .map((model) => ({
      value: model.model_id,
      label: `${model.display_name}${model.embedding_dimension ? ` (${model.embedding_dimension}d)` : ''}`,
    }))

  const vectorOptions = vectorPlan.data?.vectordbs ?? vectordbs.data ?? []
  const selectedVectorDB = vectorOptions.find((item) => item.vectordb_name === vectordbName)

  useEffect(() => {
    setChunkRunId(undefined)
    setSelectedFileIds([])
  }, [batchId])

  useEffect(() => {
    const executable = vectorOptions.find((item) => item.vectordb_name === vectordbName) ??
      vectorOptions.find((item) => item.availability_status === 'available')
    if (executable) {
      setVectordbName(executable.vectordb_name)
      setVectordbConfigText(stringifyConfig(executable.default_config))
      setEmbeddingConfigText(
        stringifyConfig({
          normalize_embeddings: Boolean(executable.default_config.normalize_embeddings),
          embedding_batch: executable.default_config.embedding_batch ?? 100,
        }),
      )
      setIndexConfigText(
        stringifyConfig({
          similarity_metric: executable.default_config.similarity_metric ?? 'cosine',
          metadata_mode: executable.default_config.metadata_mode ?? 'full',
        }),
      )
    }
  }, [vectorPlan.data])

  useEffect(() => {
    setSelectedFileIds((vectorPlan.data?.files ?? []).map((file) => file.source_file_id))
  }, [vectorPlan.data])

  const changeVectorDB = (name: string) => {
    const next = vectorOptions.find((item) => item.vectordb_name === name)
    setVectordbName(name)
    setVectordbConfigText(stringifyConfig(next?.default_config))
    setEmbeddingConfigText(
      stringifyConfig({
        normalize_embeddings: Boolean(next?.default_config.normalize_embeddings),
        embedding_batch: next?.default_config.embedding_batch ?? 100,
      }),
    )
    setIndexConfigText(
      stringifyConfig({
        similarity_metric: next?.default_config.similarity_metric ?? 'cosine',
        metadata_mode: next?.default_config.metadata_mode ?? 'full',
      }),
    )
  }

  const allFileIds = useMemo(() => (vectorPlan.data?.files ?? []).map((file) => file.source_file_id), [vectorPlan.data])
  const allSelected = allFileIds.length > 0 && selectedFileIds.length === allFileIds.length

  const columns: ColumnsType<VectorPlanFile> = [
    { title: '文件', dataIndex: 'original_filename' },
    { title: '状态', dataIndex: 'status', render: (value) => <Tag>{value}</Tag> },
    { title: 'Chunks', dataIndex: 'chunk_count' },
    { title: '字符数', dataIndex: 'char_count' },
    { title: 'Token估算', dataIndex: 'token_count' },
  ]

  const startVectorRun = () => {
    if (!batchId || !chunkRunId || !embeddingModelId || !selectedVectorDB) return
    if (!EXECUTABLE_STATUSES.has(selectedVectorDB.availability_status)) {
      message.error(`VectorDB 不可执行：${selectedVectorDB.availability_reason}`)
      return
    }
    if (useTestRelated) {
      message.error('仅测试集相关将在测试集功能完成后启用')
      return
    }
    try {
      const vectordbConfig = parseJson(vectordbConfigText)
      const embeddingConfig = parseJson(embeddingConfigText)
      const indexConfig = parseJson(indexConfigText)
      createVectorRun.mutate(
        {
          batch_id: batchId,
          chunk_run_id: chunkRunId,
          embedding_model_id: embeddingModelId,
          vectordb_name: vectordbName,
          vectordb_config: vectordbConfig,
          embedding_config: embeddingConfig,
          index_config: indexConfig,
          file_selection: { mode: 'selected', selected_file_ids: selectedFileIds },
        },
        {
          onSuccess: (run) => {
            message.success('向量化任务已启动')
            navigate(`/build/vector-runs/${run.run_id}`)
          },
          onError: (error) => message.error(error instanceof Error ? error.message : '启动失败'),
        },
      )
    } catch {
      message.error('策略 JSON 格式不正确')
    }
  }

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>材料向量化</Typography.Title>
        <Typography.Text type="secondary">
          选择已完成分块任务、嵌入模型和 VectorDB 后端，生成可复现实验向量索引。
        </Typography.Text>
      </div>
      <Card>
        <Form layout="vertical">
          <Form.Item label="材料批次">
            <Select
              placeholder="选择材料批次"
              value={batchId}
              onChange={setBatchId}
              options={(batches.data ?? []).map((batch) => ({
                value: batch.batch_id,
                label: `${batch.batch_name} (${batch.file_count} files)`,
              }))}
            />
          </Form.Item>
          <Form.Item label="分块任务">
            <Select
              placeholder="选择已完成分块任务"
              value={chunkRunId}
              disabled={!batchId}
              onChange={setChunkRunId}
              options={chunkRunOptions}
            />
          </Form.Item>
          <Form.Item label="Embedding 模型">
            <Select
              placeholder="选择 Embedded 管理中的模型"
              value={embeddingModelId}
              onChange={setEmbeddingModelId}
              options={embeddingOptions}
            />
          </Form.Item>
          <Form.Item label="VectorDB">
            <Select
              value={vectordbName}
              disabled={!chunkRunId}
              onChange={changeVectorDB}
              options={vectorOptions.map((item: VectorDB) => ({
                value: item.vectordb_name,
                disabled: !EXECUTABLE_STATUSES.has(item.availability_status),
                label: (
                  <Space>
                    <span>{item.display_name}</span>
                    <Tooltip title={item.availability_reason}>
                      <Tag color={statusColor(item.availability_status)}>{item.availability_status}</Tag>
                    </Tooltip>
                  </Space>
                ),
              }))}
            />
          </Form.Item>
          {selectedVectorDB && (
            <Alert
              showIcon
              type="info"
              message={`${selectedVectorDB.display_name} 默认存储位置：${selectedVectorDB.default_storage_uri ?? 'NA'}`}
            />
          )}
          <Form.Item label="VectorDB 配置 JSON">
            <Input.TextArea rows={8} value={vectordbConfigText} onChange={(event) => setVectordbConfigText(event.target.value)} />
          </Form.Item>
          <Form.Item label="Embedding 策略 JSON">
            <Input.TextArea rows={5} value={embeddingConfigText} onChange={(event) => setEmbeddingConfigText(event.target.value)} />
          </Form.Item>
          <Form.Item label="索引策略 JSON">
            <Input.TextArea rows={5} value={indexConfigText} onChange={(event) => setIndexConfigText(event.target.value)} />
          </Form.Item>
        </Form>
        <Button
          type="primary"
          disabled={!vectorPlan.data || !embeddingModelId || selectedFileIds.length === 0 || useTestRelated}
          loading={createVectorRun.isPending}
          onClick={startVectorRun}
        >
          开始向量化
        </Button>
      </Card>
      <Card
        title="参与向量化文件"
        extra={
          <Space>
            <Checkbox
              checked={allSelected}
              indeterminate={selectedFileIds.length > 0 && !allSelected}
              onChange={(event) => setSelectedFileIds(event.target.checked ? allFileIds : [])}
            >
              全选
            </Checkbox>
            <Checkbox checked={useTestRelated} disabled onChange={(event) => setUseTestRelated(event.target.checked)}>
              仅测试集相关
            </Checkbox>
          </Space>
        }
      >
        <Table
          rowKey="source_file_id"
          loading={vectorPlan.isLoading}
          columns={columns}
          dataSource={vectorPlan.data?.files ?? []}
          rowSelection={{
            selectedRowKeys: selectedFileIds,
            onChange: (keys) => setSelectedFileIds(keys.map(String)),
          }}
        />
      </Card>
      {batchId && (
        <Card title="同批次已有向量化任务">
          <Table
            rowKey="run_id"
            dataSource={(vectorRuns.data ?? []).filter((run) => run.batch_id === batchId)}
            columns={[
              { title: 'VectorDB', dataIndex: 'vectordb_name' },
              { title: '状态', dataIndex: 'status', render: (value) => <Tag>{value}</Tag> },
              { title: 'Vectors', dataIndex: 'total_vectors' },
              { title: 'Collection', dataIndex: 'collection_name' },
              { title: '创建时间', dataIndex: 'created_at', render: (value) => new Date(value).toLocaleString() },
            ]}
          />
        </Card>
      )}
    </Space>
  )
}
