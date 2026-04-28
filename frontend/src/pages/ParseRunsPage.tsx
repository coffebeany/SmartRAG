import { App, Card, Popconfirm, Progress, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'
import { useDeleteParseRun, useParseRuns } from '../api/hooks'
import type { ParseRun } from '../api/types'
import { TableActionButton } from '../components/TableActionButton'

export default function ParseRunsPage() {
  const { message } = App.useApp()
  const runs = useParseRuns()
  const deleteParseRun = useDeleteParseRun()

  const handleDelete = (runId: string) => {
    deleteParseRun.mutate(runId, {
      onSuccess: () => message.success('解析任务已删除'),
      onError: (error) => message.error(error instanceof Error ? error.message : '删除失败'),
    })
  }

  const columns: ColumnsType<ParseRun> = [
    { title: '批次', dataIndex: 'batch_name', render: (value, record) => value ?? record.batch_id },
    { title: '状态', dataIndex: 'status', render: (value) => <Tag>{value}</Tag> },
    {
      title: '进度',
      render: (_, record) => {
        const done = record.completed_files + record.failed_files
        const percent = record.total_files ? Math.round((done / record.total_files) * 100) : 0
        return <Progress percent={percent} size="small" format={() => `${done}/${record.total_files}`} />
      },
    },
    { title: '成功', dataIndex: 'completed_files' },
    { title: '失败', dataIndex: 'failed_files' },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      render: (value) => (value ? new Date(value).toLocaleString() : '-'),
    },
    {
      title: '操作',
      width: 180,
      render: (_, record) => (
        <Space>
          <Link to={`/build/parse-runs/${record.run_id}`}>
            <TableActionButton>查看详情</TableActionButton>
          </Link>
          <Popconfirm
            title="删除解析任务"
            description="会同步删除该任务的文件级解析记录、解析结果和本地 artifact。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => handleDelete(record.run_id)}
          >
            <TableActionButton danger loading={deleteParseRun.isPending}>
              删除
            </TableActionButton>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>解析任务</Typography.Title>
        <Typography.Text type="secondary">
          跟踪所有材料解析任务进度，完成后查看文件级详情。
        </Typography.Text>
      </div>
      <Card>
        <Table rowKey="run_id" loading={runs.isLoading} columns={columns} dataSource={runs.data ?? []} />
      </Card>
    </Space>
  )
}
