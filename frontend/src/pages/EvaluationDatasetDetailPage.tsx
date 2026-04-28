import { Card, Descriptions, Empty, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useEvaluationDatasetItems, useEvaluationDatasetRun } from '../api/hooks'
import type { EvaluationDatasetItem } from '../api/types'

function statusColor(status?: string) {
  if (status === 'completed') return 'green'
  if (status === 'failed') return 'red'
  if (status === 'running') return 'blue'
  return 'default'
}

export default function EvaluationDatasetDetailPage() {
  const { runId } = useParams()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const run = useEvaluationDatasetRun(runId)
  const items = useEvaluationDatasetItems(runId, (page - 1) * pageSize, pageSize)

  const columns: ColumnsType<EvaluationDatasetItem> = [
    { title: '问题', dataIndex: 'question', width: 320 },
    { title: '标准答案', dataIndex: 'ground_truth', width: 360 },
    { title: '来源 Chunk', dataIndex: 'source_chunk_ids', render: (value: string[]) => <Space wrap>{value.map((item) => <Tag key={item}>{item.slice(0, 8)}</Tag>)}</Space> },
    { title: '生成器', dataIndex: 'synthesizer_name', render: (value) => <Tag>{String(value ?? 'NA')}</Tag> },
    { title: '上下文数', dataIndex: 'reference_contexts', render: (value: string[]) => value.length },
  ]

  if (!run.isLoading && !run.data) {
    return <Empty description="测评集不存在" />
  }

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>测评集详情</Typography.Title>
        <Typography.Text type="secondary">查看生成任务、实际配置、问题与标准答案。</Typography.Text>
      </div>
      {run.data && (
        <Card>
          <Descriptions column={2}>
            <Descriptions.Item label="任务">{run.data.run_id}</Descriptions.Item>
            <Descriptions.Item label="状态"><Tag color={statusColor(run.data.status)}>{run.data.status}</Tag></Descriptions.Item>
            <Descriptions.Item label="批次">{run.data.batch_name ?? run.data.batch_id}</Descriptions.Item>
            <Descriptions.Item label="ChunkRun">{run.data.chunk_run_id}</Descriptions.Item>
            <Descriptions.Item label="框架">{run.data.framework_id}</Descriptions.Item>
            <Descriptions.Item label="样本">{run.data.completed_items}/{run.data.total_items}</Descriptions.Item>
          </Descriptions>
          {run.data.error_summary ? <Typography.Text type="danger">{run.data.error_summary}</Typography.Text> : null}
        </Card>
      )}
      {run.data && (
        <Card title="生成配置">
          <pre className="jsonViewer">{JSON.stringify(run.data.generator_config, null, 2)}</pre>
        </Card>
      )}
      <Card title="问题与答案">
        <Table
          rowKey="item_id"
          loading={items.isLoading}
          columns={columns}
          dataSource={items.data?.items ?? []}
          pagination={{
            current: page,
            pageSize,
            total: items.data?.total ?? 0,
            onChange: (nextPage, nextSize) => {
              setPage(nextPage)
              setPageSize(nextSize)
            },
          }}
        />
      </Card>
    </Space>
  )
}
