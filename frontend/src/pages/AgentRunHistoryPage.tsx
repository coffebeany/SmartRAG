import { DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import { App, Button, Card, Drawer, Empty, Popconfirm, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { useAgentRuns, useDeleteAgentRun, useSmartRagAgentRun } from '../api/hooks'
import type { SmartRagAgentRun } from '../api/types'
import LangfuseTraceLink from '../components/LangfuseTraceLink'

function statusColor(status?: string) {
  if (status === 'completed') return 'green'
  if (status === 'failed') return 'red'
  if (status === 'cancelled') return 'orange'
  if (status === 'running') return 'processing'
  return 'blue'
}

export default function AgentRunHistoryPage() {
  const { message } = App.useApp()
  const [detailRunId, setDetailRunId] = useState<string | undefined>()
  const runs = useAgentRuns()
  const deleteRun = useDeleteAgentRun()
  const detailQuery = useSmartRagAgentRun(detailRunId)

  const detail = detailQuery.data

  const columns: ColumnsType<SmartRagAgentRun> = [
    {
      title: '消息',
      dataIndex: 'message',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (s: string) => <Tag color={statusColor(s)}>{s}</Tag>,
    },
    {
      title: '工具调用',
      dataIndex: 'tool_logs',
      width: 80,
      render: (logs: unknown[]) => logs?.length ?? 0,
    },
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
          <Button size="small" type="link" icon={<EyeOutlined />} onClick={() => setDetailRunId(record.run_id)}>
            详情
          </Button>
          <Popconfirm
            title="确认删除此对话记录？"
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
        <Typography.Title level={3}>Agent 对话历史</Typography.Title>
        <Typography.Text type="secondary">查看和管理 SmartRAG Agent 的历史对话记录和 Langfuse 观测链接。</Typography.Text>
      </div>
      <Card>
        <Space style={{ marginBottom: 12 }}>
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
          locale={{ emptyText: <Empty description="暂无对话记录" /> }}
        />
      </Card>

      <Drawer
        title="对话详情"
        width={720}
        open={Boolean(detailRunId)}
        onClose={() => setDetailRunId(undefined)}
        loading={detailQuery.isLoading}
      >
        {detail && (
          <Space direction="vertical" size={16} className="fullWidth">
            <Card size="small" title="基本信息">
              <Space direction="vertical" size={4}>
                <Typography.Text strong>用户消息:</Typography.Text>
                <Typography.Paragraph>{detail.message}</Typography.Paragraph>
                <Typography.Text>状态: <Tag color={statusColor(detail.status)}>{detail.status}</Tag></Typography.Text>
                <LangfuseTraceLink traceId={detail.langfuse_trace_id} />
                {detail.error && <Typography.Text type="danger">错误: {detail.error}</Typography.Text>}
              </Space>
            </Card>
            {detail.answer && (
              <Card size="small" title="Agent 回答">
                <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>{detail.answer}</Typography.Paragraph>
              </Card>
            )}
            {detail.tool_logs.length > 0 && (
              <Card size="small" title={`工具调用 (${detail.tool_logs.length})`}>
                <Space direction="vertical" size={8} className="fullWidth">
                  {detail.tool_logs.map((log) => (
                    <Card key={log.tool_log_id} size="small" type="inner">
                      <Space direction="vertical" size={4} className="fullWidth">
                        <Space wrap>
                          <Typography.Text strong>{log.tool_name}</Typography.Text>
                          <Tag color={log.status === 'success' ? 'green' : log.status === 'error' ? 'red' : 'blue'}>
                            {log.status}
                          </Tag>
                          {log.latency_ms != null && (
                            <Typography.Text type="secondary">{log.latency_ms}ms</Typography.Text>
                          )}
                        </Space>
                      </Space>
                    </Card>
                  ))}
                </Space>
              </Card>
            )}
          </Space>
        )}
      </Drawer>
    </Space>
  )
}
