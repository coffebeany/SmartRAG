import { App, Button, Card, Form, Input, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useChunkPlan,
  useChunkRuns,
  useChunkStrategies,
  useCreateChunkRun,
  useMaterialBatches,
  useModels,
  useParseRuns,
} from '../api/hooks'
import type { ChunkPlanFile, ChunkStrategy } from '../api/types'

const EXECUTABLE_STATUSES = new Set(['available', 'needs_config'])

function stringifyConfig(config: Record<string, unknown> | undefined) {
  return JSON.stringify(config ?? {}, null, 2)
}

function statusColor(status?: string) {
  if (status === 'available') return 'green'
  if (status === 'needs_config') return 'gold'
  if (status === 'adapter_only') return 'blue'
  return 'red'
}

export default function MaterialChunkPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [batchId, setBatchId] = useState<string>()
  const [parseRunId, setParseRunId] = useState<string>()
  const [chunkerName, setChunkerName] = useState<string>()
  const [configText, setConfigText] = useState('{}')
  const batches = useMaterialBatches()
  const parseRuns = useParseRuns()
  const chunkers = useChunkStrategies()
  const models = useModels()
  const chunkPlan = useChunkPlan(batchId, parseRunId)
  const createChunkRun = useCreateChunkRun()
  const chunkRuns = useChunkRuns()

  const parseRunOptions = (parseRuns.data ?? [])
    .filter((run) => run.batch_id === batchId && ['completed', 'completed_with_errors'].includes(run.status))
    .map((run) => ({
      value: run.run_id,
      label: `${run.batch_name ?? run.batch_id} / ${run.status} / ${new Date(run.created_at).toLocaleString()}`,
    }))

  const selectedChunker = (chunkPlan.data?.chunk_options ?? chunkers.data ?? []).find(
    (item) => item.chunker_name === chunkerName,
  )

  useEffect(() => {
    setParseRunId(undefined)
    setChunkerName(undefined)
  }, [batchId])

  useEffect(() => {
    const first = chunkPlan.data?.chunk_options.find((item) => EXECUTABLE_STATUSES.has(item.availability_status))
    if (first && !chunkerName) {
      setChunkerName(first.chunker_name)
      setConfigText(stringifyConfig(first.default_config))
    }
  }, [chunkPlan.data, chunkerName])

  const changeChunker = (name: string) => {
    const next = (chunkPlan.data?.chunk_options ?? chunkers.data ?? []).find((item) => item.chunker_name === name)
    setChunkerName(name)
    setConfigText(stringifyConfig(next?.default_config))
  }

  const columns: ColumnsType<ChunkPlanFile> = useMemo(
    () => [
      { title: '文件', dataIndex: 'original_filename' },
      { title: 'Parser', dataIndex: 'parser_name' },
      { title: '字符数', dataIndex: 'char_count' },
      { title: '页数', dataIndex: 'pages', render: (value) => (value >= 0 ? value : '-') },
    ],
    [],
  )

  const startChunk = () => {
    if (!batchId || !parseRunId || !chunkerName || !selectedChunker) return
    try {
      const config = JSON.parse(configText || '{}')
      if (selectedChunker.requires_embedding_model && !config.embedding_model_id) {
        message.error('语义分块需要在配置中选择 embedding_model_id')
        return
      }
      createChunkRun.mutate(
        { batch_id: batchId, parse_run_id: parseRunId, chunker_name: chunkerName, chunker_config: config },
        {
          onSuccess: (run) => {
            message.success('分块任务已启动')
            navigate(`/build/chunk-runs/${run.run_id}`)
          },
          onError: (error) => message.error(error instanceof Error ? error.message : '启动失败'),
        },
      )
    } catch {
      message.error('配置 JSON 格式不正确')
    }
  }

  const embeddingOptions = (models.data ?? [])
    .filter((model) => model.model_category === 'embedding' && model.enabled)
    .map((model) => ({ value: model.model_id, label: model.display_name }))

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>材料分块</Typography.Title>
        <Typography.Text type="secondary">
          选择材料批次和已完成解析任务，再用一个分块策略生成标准 chunk 结果。
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
          <Form.Item label="解析任务">
            <Select
              placeholder="选择已完成解析任务"
              value={parseRunId}
              disabled={!batchId}
              onChange={setParseRunId}
              options={parseRunOptions}
            />
          </Form.Item>
          <Form.Item label="分块工具">
            <Select
              placeholder="选择分块工具"
              value={chunkerName}
              disabled={!parseRunId}
              onChange={changeChunker}
              options={(chunkPlan.data?.chunk_options ?? []).map((chunker) => ({
                value: chunker.chunker_name,
                disabled: !EXECUTABLE_STATUSES.has(chunker.availability_status),
                label: (
                  <Space>
                    <span>{chunker.display_name}</span>
                    <Tooltip title={chunker.availability_reason}>
                      <Tag color={statusColor(chunker.availability_status)}>{chunker.availability_status}</Tag>
                    </Tooltip>
                  </Space>
                ),
              }))}
            />
          </Form.Item>
          {selectedChunker?.requires_embedding_model && (
            <Form.Item label="Embedding 模型">
              <Select
                placeholder="选择 embedding 模型"
                options={embeddingOptions}
                onChange={(value) => {
                  let current: Record<string, unknown> = {}
                  try {
                    current = JSON.parse(configText || '{}')
                  } catch {
                    current = {}
                  }
                  setConfigText(stringifyConfig({ ...current, embedding_model_id: value }))
                }}
              />
            </Form.Item>
          )}
          <Form.Item label="配置 JSON">
            <Input.TextArea rows={8} value={configText} onChange={(event) => setConfigText(event.target.value)} />
          </Form.Item>
        </Form>
        <Button
          type="primary"
          disabled={!chunkPlan.data || !chunkerName || chunkPlan.data.files.length === 0}
          loading={createChunkRun.isPending}
          onClick={startChunk}
        >
          开始分块
        </Button>
      </Card>
      <Card title="待分块文件">
        <Table
          rowKey="parsed_document_id"
          loading={chunkPlan.isLoading}
          columns={columns}
          dataSource={chunkPlan.data?.files ?? []}
          pagination={false}
        />
      </Card>
      {batchId && (
        <Card title="同批次已有分块任务">
          <Table
            rowKey="run_id"
            dataSource={(chunkRuns.data ?? []).filter((run) => run.batch_id === batchId)}
            columns={[
              { title: '工具', dataIndex: 'chunker_name' },
              { title: '状态', dataIndex: 'status', render: (value) => <Tag>{value}</Tag> },
              { title: 'Chunks', dataIndex: 'total_chunks' },
              { title: '创建时间', dataIndex: 'created_at', render: (value) => new Date(value).toLocaleString() },
            ]}
          />
        </Card>
      )}
    </Space>
  )
}
