import { App, Card, Popconfirm, Progress, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'
import { useDeleteEvaluationDatasetRun, useEvaluationDatasetRuns } from '../api/hooks'
import type { EvaluationDatasetRun } from '../api/types'
import { TableActionButton } from '../components/TableActionButton'

function progress(run: EvaluationDatasetRun) {
  const done = run.completed_items + run.failed_items
  return run.total_items ? Math.round((done / run.total_items) * 100) : 0
}

function statusColor(status: string) {
  if (status === 'completed') return 'green'
  if (status === 'failed') return 'red'
  if (status === 'completed_with_errors') return 'orange'
  if (status === 'running') return 'blue'
  return 'default'
}

export default function EvaluationDatasetRunsPage() {
  const { message } = App.useApp()
  const datasetRuns = useEvaluationDatasetRuns()
  const deleteRun = useDeleteEvaluationDatasetRun()

  const columns: ColumnsType<EvaluationDatasetRun> = [
    {
      title: '测评集',
      dataIndex: 'display_name',
      width: 360,
      render: (value, record) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{value ?? record.batch_name ?? record.batch_id}</Typography.Text>
          <Typography.Text type="secondary" code>{record.run_id.slice(0, 8)}</Typography.Text>
        </Space>
      ),
    },
    { title: '框架', dataIndex: 'framework_id', width: 100, render: (value) => <Tag>{String(value)}</Tag> },
    { title: '状态', dataIndex: 'status', width: 140, render: (value) => <Tag color={statusColor(String(value))}>{String(value)}</Tag> },
    { title: '进度', width: 180, render: (_, record) => <Progress size="small" percent={progress(record)} format={() => `${record.completed_items}/${record.total_items}`} /> },
    { title: '错误', dataIndex: 'error_summary', ellipsis: true },
    {
      title: '操作',
      width: 170,
      render: (_, record) => (
        <Space>
          <Link className="tableActionLink" to={`/build/evaluation-dataset-runs/${record.run_id}`}>查看</Link>
          <Popconfirm
            title="删除测评集"
            description="会同步删除该测评集、样本明细及其关联测评报告。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => deleteRun.mutate(record.run_id, {
              onSuccess: () => message.success('测评集已删除'),
              onError: (error) => message.error(error instanceof Error ? error.message : '删除失败'),
            })}
          >
            <TableActionButton danger disabled={['pending', 'running'].includes(record.status)} loading={deleteRun.isPending}>删除</TableActionButton>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>测评集任务</Typography.Title>
        <Typography.Text type="secondary">查看测评集生成进度，进入详情维护问题与标准答案。</Typography.Text>
      </div>
      <Card>
        <Table rowKey="run_id" loading={datasetRuns.isLoading} columns={columns} dataSource={datasetRuns.data ?? []} />
      </Card>
    </Space>
  )
}
