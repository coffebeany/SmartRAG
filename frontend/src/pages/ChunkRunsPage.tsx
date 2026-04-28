import { App, Button, Card, Popconfirm, Progress, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'
import { useChunkRuns, useDeleteChunkRun } from '../api/hooks'
import type { ChunkRun } from '../api/types'

export default function ChunkRunsPage() {
  const { message } = App.useApp()
  const runs = useChunkRuns()
  const deleteChunkRun = useDeleteChunkRun()

  const handleDelete = (runId: string) => {
    deleteChunkRun.mutate(runId, {
      onSuccess: () => message.success('分块任务已删除'),
      onError: (error) => message.error(error instanceof Error ? error.message : '删除失败'),
    })
  }

  const columns: ColumnsType<ChunkRun> = [
    { title: '批次', dataIndex: 'batch_name', render: (value, record) => value ?? record.batch_id },
    { title: '分块工具', dataIndex: 'chunker_name' },
    { title: '状态', dataIndex: 'status', render: (value) => <Tag>{value}</Tag> },
    {
      title: '进度',
      render: (_, record) => {
        const done = record.completed_files + record.failed_files
        const percent = record.total_files ? Math.round((done / record.total_files) * 100) : 0
        return <Progress percent={percent} size="small" format={() => `${done}/${record.total_files}`} />
      },
    },
    { title: 'Chunks', dataIndex: 'total_chunks' },
    { title: '失败', dataIndex: 'failed_files' },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      render: (value) => (value ? new Date(value).toLocaleString() : '-'),
    },
    {
      title: '操作',
      width: 200,
      render: (_, record) => (
        <Space>
          <Link to={`/build/chunk-runs/${record.run_id}`}>
            <Button>查看详情</Button>
          </Link>
          <Popconfirm
            title="删除分块任务"
            description="会同步删除该任务的文件级分块记录、chunk 结果和本地 artifact。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => handleDelete(record.run_id)}
          >
            <Button danger loading={deleteChunkRun.isPending}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>分块任务</Typography.Title>
        <Typography.Text type="secondary">跟踪材料批次分块进度，完成后查看文件级 chunk 结果。</Typography.Text>
      </div>
      <Card>
        <Table rowKey="run_id" loading={runs.isLoading} columns={columns} dataSource={runs.data ?? []} />
      </Card>
    </Space>
  )
}
