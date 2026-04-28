import { Alert, App, Button, Card, Form, Popconfirm, Progress, Select, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  useCreateEvaluationReportRun,
  useDeleteEvaluationReportRun,
  useEvaluationDatasetRuns,
  useEvaluationFrameworks,
  useEvaluationReportRuns,
  useRagFlows,
  useVectorRuns,
} from '../api/hooks'
import type { EvaluationDatasetRun, EvaluationReportRun, RagFlow } from '../api/types'
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

function hasAnswerGenerator(flow?: RagFlow) {
  return Boolean(flow?.nodes.some((node) => node.enabled && node.node_type === 'answer_generator'))
}

export default function EvaluationReportsPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const frameworks = useEvaluationFrameworks()
  const flows = useRagFlows()
  const vectorRuns = useVectorRuns()
  const datasets = useEvaluationDatasetRuns()
  const reports = useEvaluationReportRuns()
  const createReport = useCreateEvaluationReportRun()
  const deleteReport = useDeleteEvaluationReportRun()
  const frameworkId = Form.useWatch('framework_id', form) ?? 'ragas'
  const flowId = Form.useWatch('flow_id', form)
  const framework = (frameworks.data ?? []).find((item) => item.framework_id === frameworkId)
  const selectedFlow = (flows.data ?? []).find((flow) => flow.flow_id === flowId)
  const selectedVector = (vectorRuns.data ?? []).find((run) => run.run_id === selectedFlow?.vector_run_id)
  const datasetOptions = (datasets.data ?? [])
    .filter((run: EvaluationDatasetRun) => run.status === 'completed' && (!selectedVector || run.chunk_run_id === selectedVector.chunk_run_id))
    .map((run) => ({ value: run.run_id, label: `${run.batch_name ?? run.batch_id} / ${run.completed_items} samples / ${run.framework_id}` }))
  const metricOptions = ['retrieval', 'retrieval_id', 'generation'].map((category) => ({
    label: category === 'retrieval_id' ? 'Chunk ID Retrieval' : category,
    options: (framework?.metrics ?? [])
      .filter((metric) => metric.category === category)
      .map((metric) => ({ value: metric.metric_id, label: `${metric.display_name} (${metric.metric_id})` })),
  })).filter((group) => group.options.length)

  useEffect(() => {
    const current = form.getFieldValue('metric_ids')
    if ((!current || !current.length) && framework?.default_metrics?.length) {
      form.setFieldValue('metric_ids', framework.default_metrics)
    }
  }, [form, framework])

  const submit = async () => {
    try {
      const values = await form.validateFields()
      createReport.mutate(
        {
          flow_id: values.flow_id,
          dataset_run_id: values.dataset_run_id,
          framework_id: values.framework_id,
          metric_ids: values.metric_ids,
          evaluator_config: {},
        },
        { onSuccess: () => message.success('测评报告任务已创建'), onError: (error) => message.error(error instanceof Error ? error.message : '创建失败') },
      )
    } catch {
      message.error('请检查测评配置')
    }
  }

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
        <Typography.Title level={3}>应用测评</Typography.Title>
        <Typography.Text type="secondary">在指定 RAG 流程上运行测评集并生成报告。</Typography.Text>
      </div>
      <Card title="创建报告">
        <Form form={form} layout="vertical" initialValues={{ framework_id: 'ragas', metric_ids: framework?.default_metrics ?? [] }}>
          {framework?.availability_status !== 'available' && framework ? (
            <Alert type="warning" showIcon message={framework.availability_reason} description={framework.dependency_install_hint} />
          ) : null}
          <Form.Item name="framework_id" label="测评框架" rules={[{ required: true }]}>
            <Select
              options={(frameworks.data ?? []).map((item) => ({
                value: item.framework_id,
                label: `${item.display_name} / ${item.availability_status}`,
                disabled: item.availability_status !== 'available',
              }))}
              onChange={(value) => {
                const next = (frameworks.data ?? []).find((item) => item.framework_id === value)
                form.setFieldValue('metric_ids', next?.default_metrics ?? [])
              }}
            />
          </Form.Item>
          <Form.Item name="flow_id" label="RAG 流程" rules={[{ required: true }]}>
            <Select
              options={(flows.data ?? []).map((flow) => ({
                value: flow.flow_id,
                disabled: !hasAnswerGenerator(flow),
                label: `${flow.flow_name}${hasAnswerGenerator(flow) ? '' : ' / 需要 answer_generator'}`,
              }))}
            />
          </Form.Item>
          {selectedFlow && !hasAnswerGenerator(selectedFlow) ? <Alert type="warning" showIcon message="该流程需要先在流程构建中增加 answer_generator 节点。" /> : null}
          <Form.Item name="dataset_run_id" label="测评集" rules={[{ required: true }]}>
            <Select options={datasetOptions} />
          </Form.Item>
          <Form.Item name="metric_ids" label="指标" rules={[{ required: true }]}>
            <Select mode="multiple" options={metricOptions} />
          </Form.Item>
          <Button type="primary" loading={createReport.isPending} onClick={submit}>创建测评报告</Button>
        </Form>
      </Card>
      <Card title="报告列表">
        <Table rowKey="run_id" loading={reports.isLoading} columns={columns} dataSource={reports.data ?? []} />
      </Card>
    </Space>
  )
}
