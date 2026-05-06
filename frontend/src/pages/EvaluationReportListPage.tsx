import { App, Popconfirm, Progress, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'
import {
  useDeleteEvaluationReportRun,
  useEvaluationReportRuns,
} from '../api/hooks'
import type { EvaluationReportRun } from '../api/types'
import { MetricScoreGrid } from '../components/MetricScoreGrid'
import { TableActionButton } from '../components/TableActionButton'

function statusColor(status: string) {
  if (status === 'completed') return 'green'
  if (status === 'completed_with_errors') return 'orange'
  if (status === 'failed') return 'red'
  if (status === 'running') return 'blue'
  return 'default'
}

function progress(run: EvaluationReportRun) {
  const done = run.completed_items + run.failed_items
  return run.total_items ? Math.round((done / run.total_items) * 100) : 0
}

export default function EvaluationReportListPage() {
  const { message } = App.useApp()
  const reports = useEvaluationReportRuns()
  const deleteReport = useDeleteEvaluationReportRun()

  const columns: ColumnsType<EvaluationReportRun> = [
    { title: '任务', dataIndex: 'run_id', render: (value) => <Typography.Text code>{String(value).slice(0, 8)}</Typography.Text> },
    { title: '流程', dataIndex: 'flow_name' },
    { title: '框架', dataIndex: 'framework_id', render: (value) => <Tag>{String(value)}</Tag> },
    { title: '状态', dataIndex: 'status', render: (value) => <Tag color={statusColor(String(value))}>{String(value)}</Tag> },
    { title: '进度', render: (_, record) => <Progress size="small" percent={progress(record)} format={() => `${record.completed_items}/${record.total_items}`} /> },
    { title: '指标', dataIndex: 'aggregate_scores', width: 360, render: (value: Record<string, number>) => <MetricScoreGrid scores={value} compact /> },
    {
      title: '操作',
      width: 170,
      render: (_, record) => (
        <Space>
          <Link className="tableActionLink" to={`/build/evaluation-reports/${record.run_id}`}>查看</Link>
          <Popconfirm
            title="删除测评报告"
            description="会同步删除报告明细和该报告产生的流程执行记录。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => deleteReport.mutate(record.run_id, {
              onSuccess: () => message.success('测评报告已删除'),
              onError: (error) => message.error(error instanceof Error ? error.message : '删除失败'),
            })}
          >
            <TableActionButton danger disabled={['pending', 'running'].includes(record.status)} loading={deleteReport.isPending}>删除</TableActionButton>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>测评报告</Typography.Title>
        <Typography.Text type="secondary">查看所有应用测评生成的报告。</Typography.Text>
      </div>
      <Table rowKey="run_id" loading={reports.isLoading} columns={columns} dataSource={reports.data ?? []} />
    </Space>
  )
}
