import { Card, Descriptions, Empty, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useEvaluationReportItems, useEvaluationReportRun } from '../api/hooks'
import type { EvaluationReportItem } from '../api/types'

function statusColor(status?: string) {
  if (status === 'completed') return 'green'
  if (status === 'completed_with_errors') return 'orange'
  if (status === 'failed') return 'red'
  if (status === 'running') return 'blue'
  return 'default'
}

export default function EvaluationReportDetailPage() {
  const { runId } = useParams()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const run = useEvaluationReportRun(runId)
  const items = useEvaluationReportItems(runId, (page - 1) * pageSize, pageSize)

  const columns: ColumnsType<EvaluationReportItem> = [
    { title: '问题', dataIndex: 'question', width: 260 },
    { title: '回答', dataIndex: 'answer', width: 360, render: (value) => String(value ?? '') },
    { title: '分数', dataIndex: 'scores', render: (value: Record<string, number>) => <Space wrap>{Object.entries(value ?? {}).map(([key, score]) => <Tag key={key}>{key}: {Number(score).toFixed(3)}</Tag>)}</Space> },
    { title: '上下文', dataIndex: 'contexts', render: (value: string[]) => value.length },
    { title: '延迟', dataIndex: 'latency_ms', render: (value) => value ? `${value} ms` : 'NA' },
    { title: '错误', dataIndex: 'error', ellipsis: true },
  ]

  if (!run.isLoading && !run.data) {
    return <Empty description="报告不存在" />
  }

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>测评报告</Typography.Title>
        <Typography.Text type="secondary">查看聚合指标、逐样本答案、上下文与节点 trace。</Typography.Text>
      </div>
      {run.data && (
        <Card>
          <Descriptions column={2}>
            <Descriptions.Item label="任务">{run.data.run_id}</Descriptions.Item>
            <Descriptions.Item label="状态"><Tag color={statusColor(run.data.status)}>{run.data.status}</Tag></Descriptions.Item>
            <Descriptions.Item label="流程">{run.data.flow_name ?? run.data.flow_id}</Descriptions.Item>
            <Descriptions.Item label="测评集">{run.data.dataset_run_id}</Descriptions.Item>
            <Descriptions.Item label="框架">{run.data.framework_id}</Descriptions.Item>
            <Descriptions.Item label="样本">{run.data.completed_items}/{run.data.total_items}</Descriptions.Item>
          </Descriptions>
          {run.data.error_summary ? <Typography.Text type="danger">{run.data.error_summary}</Typography.Text> : null}
        </Card>
      )}
      {run.data && (
        <Card title="聚合指标">
          <Space wrap>
            {Object.entries(run.data.aggregate_scores ?? {}).map(([key, value]) => (
              <Tag key={key}>{key}: {Number(value).toFixed(4)}</Tag>
            ))}
            {!Object.keys(run.data.aggregate_scores ?? {}).length ? <Typography.Text type="secondary">暂无分数</Typography.Text> : null}
          </Space>
        </Card>
      )}
      <Card title="样本明细">
        <Table
          rowKey="item_id"
          loading={items.isLoading}
          columns={columns}
          dataSource={items.data?.items ?? []}
          expandable={{
            expandedRowRender: (record) => (
              <Space direction="vertical" className="fullWidth">
                <Typography.Text strong>Retrieved Chunk IDs</Typography.Text>
                <Space wrap>{record.retrieved_chunk_ids.map((item) => <Tag key={item}>{item.slice(0, 8)}</Tag>)}</Space>
                <Typography.Text strong>Contexts</Typography.Text>
                {record.contexts.map((context, index) => <Typography.Paragraph key={`${record.item_id}-${index}`} className="passageText">{context}</Typography.Paragraph>)}
                <Typography.Text strong>Trace</Typography.Text>
                <pre className="jsonViewer">{JSON.stringify(record.trace_events, null, 2)}</pre>
              </Space>
            ),
          }}
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
