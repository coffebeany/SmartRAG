import { Button, Popconfirm, Progress, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'
import { useDeleteVectorRun, useVectorRuns } from '../api/hooks'
import type { VectorRun } from '../api/types'

export default function VectorRunsPage() {
  const runs = useVectorRuns()
  const deleteVectorRun = useDeleteVectorRun()

  const columns: ColumnsType<VectorRun> = [
    { title: '批次', dataIndex: 'batch_name', render: (value, record) => value ?? record.batch_id },
    { title: 'VectorDB', dataIndex: 'vectordb_name' },
    {
      title: 'Embedding',
      dataIndex: 'embedding_model_snapshot',
      render: (value: Record<string, unknown>) => String(value?.display_name ?? value?.model_name ?? 'NA'),
    },
    { title: '状态', dataIndex: 'status', render: (value) => <Tag>{value}</Tag> },
    {
      title: '进度',
      render: (_, record) => (
        <Progress
          percent={record.total_files ? Math.round((record.completed_files / record.total_files) * 100) : 0}
          size="small"
        />
      ),
    },
    { title: '文件', render: (_, record) => `${record.completed_files}/${record.total_files}` },
    { title: 'Vectors', dataIndex: 'total_vectors' },
    { title: 'Collection', dataIndex: 'collection_name' },
    { title: '创建时间', dataIndex: 'created_at', render: (value) => new Date(value).toLocaleString() },
    {
      title: '操作',
      render: (_, record) => (
        <Space>
          <Link to={`/build/vector-runs/${record.run_id}`}>详情</Link>
          <Popconfirm title="删除任务并同步删除外部 collection？" onConfirm={() => deleteVectorRun.mutate(record.run_id)}>
            <Button danger loading={deleteVectorRun.isPending}>
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
        <Typography.Title level={3}>向量化任务</Typography.Title>
        <Typography.Text type="secondary">查看批次向量化进度、策略和外部 VectorDB collection。</Typography.Text>
      </div>
      <Table rowKey="run_id" loading={runs.isLoading} columns={columns} dataSource={runs.data ?? []} />
    </Space>
  )
}
