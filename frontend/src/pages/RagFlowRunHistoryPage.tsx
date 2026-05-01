import { DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import { App, Button, Card, Drawer, Empty, Popconfirm, Select, Space, Table, Tag, Timeline, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMemo, useState } from 'react'
import { useDeleteRagFlowRun, useRagFlows, useRagFlowRuns } from '../api/hooks'
import { apiClient } from '../api/client'
import type { RagFlowRun, RagFlowRunSummary } from '../api/types'
import LangfuseTraceLink from '../components/LangfuseTraceLink'

function statusColor(status?: string) {
  if (status === 'completed') return 'green'
  if (status === 'failed') return 'red'
  return 'blue'
}

function titleCase(value: unknown) {
  return String(value ?? '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export default function RagFlowRunHistoryPage() {
  const { message } = App.useApp()
  const [flowId, setFlowId] = useState<string | undefined>()
  const [detailRunId, setDetailRunId] = useState<string | undefined>()
  const [detailData, setDetailData] = useState<RagFlowRun | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const flows = useRagFlows()
  const runs = useRagFlowRuns(flowId)
  const deleteRun = useDeleteRagFlowRun()

  const flowOptions = useMemo(
    () => [
      { label: '全部流程', value: '' },
      ...(flows.data ?? []).map((f) => ({ label: f.flow_name, value: f.flow_id })),
    ],
    [flows.data],
  )

  const flowNameMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const f of flows.data ?? []) map[f.flow_id] = f.flow_name
    return map
  }, [flows.data])

  const openDetail = async (runId: string) => {
    setDetailRunId(runId)
    setDetailLoading(true)
    try {
      const data = await apiClient.get<RagFlowRun>(`/rag-flow-runs/${runId}`)
      setDetailData(data)
    } catch {
      message.error('Failed to load run detail')
    } finally {
      setDetailLoading(false)
    }
  }

  const columns: ColumnsType<RagFlowRunSummary> = [
    {
      title: '流程',
      dataIndex: 'flow_id',
      width: 140,
      render: (fid: string) => flowNameMap[fid] || fid.slice(0, 8),
    },
    { title: '问题', dataIndex: 'query', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (s: string) => <Tag color={statusColor(s)}>{s}</Tag>,
    },
    { title: '耗时', dataIndex: 'latency_ms', width: 80, render: (v: number | null) => (v != null ? `${v}ms` : '-') },
    {
      title: '时间',
      dataIndex: 'created_at',
      width: 170,
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: 'Langfuse',
      dataIndex: 'langfuse_trace_id',
      width: 90,
      render: (id: string | null) => <LangfuseTraceLink traceId={id} />,
    },
    {
      title: '操作',
      width: 110,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" type="link" icon={<EyeOutlined />} onClick={() => openDetail(record.run_id)}>
            详情
          </Button>
          <Popconfirm
            title="确认删除此运行记录？"
            onConfirm={() => deleteRun.mutateAsync(record.run_id).then(() => message.success('已删除'))}
          >
            <Button size="small" type="link" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>流程体验历史</Typography.Title>
        <Typography.Text type="secondary">查看和管理 RAG 流程的历史运行记录和 Langfuse 观测链接。</Typography.Text>
      </div>
      <Card>
        <Space style={{ marginBottom: 12 }}>
          <Select
            style={{ width: 260 }}
            placeholder="筛选流程"
            value={flowId ?? ''}
            onChange={(v) => setFlowId(v || undefined)}
            options={flowOptions}
          />
          <Button onClick={() => runs.refetch()} loading={runs.isFetching}>
            刷新
          </Button>
        </Space>
        <Table
          rowKey="run_id"
          columns={columns}
          dataSource={runs.data ?? []}
          loading={runs.isLoading}
          pagination={{ pageSize: 20 }}
          size="small"
          locale={{ emptyText: <Empty description="暂无运行记录" /> }}
        />
      </Card>

      <Drawer
        title="运行详情"
        width={720}
        open={Boolean(detailRunId)}
        onClose={() => { setDetailRunId(undefined); setDetailData(null) }}
        loading={detailLoading}
      >
        {detailData && (
          <Space direction="vertical" size={16} className="fullWidth">
            <Card size="small" title="基本信息">
              <Space direction="vertical" size={4}>
                <Typography.Text>问题: {detailData.query}</Typography.Text>
                <Typography.Text>状态: <Tag color={statusColor(detailData.status)}>{detailData.status}</Tag></Typography.Text>
                <Typography.Text>耗时: {detailData.latency_ms ?? '-'}ms</Typography.Text>
                <LangfuseTraceLink traceId={detailData.langfuse_trace_id} />
                {detailData.error && <Typography.Text type="danger">错误: {detailData.error}</Typography.Text>}
              </Space>
            </Card>
            {detailData.answer && (
              <Card size="small" title="回答">
                <Typography.Paragraph>{detailData.answer}</Typography.Paragraph>
              </Card>
            )}
            <Card size="small" title="Trace Events">
              <Timeline
                items={(detailData.trace_events ?? []).map((event, i) => ({
                  color: statusColor(event.status as string),
                  children: (
                    <Space direction="vertical" size={4}>
                      <Space wrap>
                        <Typography.Text strong>{titleCase(event.node_type)}</Typography.Text>
                        <Tag>{String(event.module_type)}</Tag>
                        <Tag color={statusColor(event.status as string)}>{String(event.status)}</Tag>
                        <Typography.Text type="secondary">{String(event.latency_ms ?? 0)}ms</Typography.Text>
                      </Space>
                    </Space>
                  ),
                  key: `${i}-${event.node_type}`,
                }))}
              />
            </Card>
          </Space>
        )}
      </Drawer>
    </Space>
  )
}
