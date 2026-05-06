import { Alert, App, Button, Card, Form, Select, Space, Typography } from 'antd'
import { useEffect } from 'react'
import {
  useBatchCreateEvaluationReportRuns,
  useEvaluationDatasetRuns,
  useEvaluationFrameworks,
  useRagFlows,
  useVectorRuns,
} from '../api/hooks'
import type { EvaluationDatasetRun, RagFlow } from '../api/types'

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
  const batchCreate = useBatchCreateEvaluationReportRuns()
  const frameworkId = Form.useWatch('framework_id', form) ?? 'ragas'
  const flowIds: string[] = Form.useWatch('flow_ids', form) ?? []
  const framework = (frameworks.data ?? []).find((item) => item.framework_id === frameworkId)

  const selectedFlows = (flows.data ?? []).filter((flow) => flowIds.includes(flow.flow_id))
  const firstSelectedFlow = selectedFlows[0]
  const selectedVector = firstSelectedFlow
    ? (vectorRuns.data ?? []).find((run) => run.run_id === firstSelectedFlow.vector_run_id)
    : undefined

  const datasetOptions = (datasets.data ?? [])
    .filter((run: EvaluationDatasetRun) => run.status === 'completed' && (!selectedVector || run.chunk_run_id === selectedVector.chunk_run_id))
    .map((run) => ({
      value: run.run_id,
      label: run.display_name ?? `${run.batch_name ?? run.batch_id} / ${run.completed_items} samples / ${run.framework_id} / ${run.run_id.slice(0, 8)}`,
    }))
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

  const invalidFlows = selectedFlows.filter((flow) => !hasAnswerGenerator(flow))

  const submit = async () => {
    try {
      const values = await form.validateFields()
      batchCreate.mutate(
        {
          flow_ids: values.flow_ids,
          dataset_run_id: values.dataset_run_id,
          framework_id: values.framework_id,
          metric_ids: values.metric_ids,
          evaluator_config: {},
        },
        {
          onSuccess: (runs) => message.success(`已创建 ${runs.length} 个测评报告任务`),
          onError: (error) => message.error(error instanceof Error ? error.message : '创建失败'),
        },
      )
    } catch {
      message.error('请检查测评配置')
    }
  }

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>应用测评</Typography.Title>
        <Typography.Text type="secondary">选择多个 RAG 流程，统一应用同一个测评集批量生成测评报告。</Typography.Text>
      </div>
      <Card title="批量创建报告">
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
          <Form.Item name="flow_ids" label="RAG 流程（可多选）" rules={[{ required: true, type: 'array', min: 1, message: '请至少选择一个流程' }]}>
            <Select
              mode="multiple"
              options={(flows.data ?? []).map((flow) => ({
                value: flow.flow_id,
                disabled: !hasAnswerGenerator(flow),
                label: `${flow.flow_name}${hasAnswerGenerator(flow) ? '' : ' / 需要 answer_generator'}`,
              }))}
            />
          </Form.Item>
          {invalidFlows.length > 0 ? (
            <Alert
              type="warning"
              showIcon
              message={`以下流程需要先在流程构建中增加 answer_generator 节点：${invalidFlows.map((f) => f.flow_name).join('、')}`}
            />
          ) : null}
          <Form.Item name="dataset_run_id" label="测评集" rules={[{ required: true }]}>
            <Select showSearch optionFilterProp="label" popupMatchSelectWidth={520} options={datasetOptions} />
          </Form.Item>
          <Form.Item name="metric_ids" label="指标" rules={[{ required: true }]}>
            <Select mode="multiple" options={metricOptions} />
          </Form.Item>
          <Button type="primary" loading={batchCreate.isPending} onClick={submit}>
            批量创建测评报告{flowIds.length > 1 ? ` (${flowIds.length} 个流程)` : ''}
          </Button>
        </Form>
      </Card>
    </Space>
  )
}
