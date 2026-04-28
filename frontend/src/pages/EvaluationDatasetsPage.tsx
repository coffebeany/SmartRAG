import { Alert, App, Button, Card, Collapse, Form, Input, InputNumber, Select, Space, Typography } from 'antd'
import { useEffect } from 'react'
import {
  useChunkRuns,
  useCreateEvaluationDatasetRun,
  useEvaluationFrameworks,
  useMaterialBatches,
  useModelDefaults,
  useModels,
} from '../api/hooks'
import type { ChunkRun } from '../api/types'

function parseJson(text: string) {
  try {
    return JSON.parse(text || '{}')
  } catch {
    throw new Error('高级 JSON 格式不正确')
  }
}

export default function EvaluationDatasetsPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const batches = useMaterialBatches()
  const chunkRuns = useChunkRuns()
  const models = useModels()
  const defaults = useModelDefaults()
  const frameworks = useEvaluationFrameworks()
  const createRun = useCreateEvaluationDatasetRun()

  const framework = (frameworks.data ?? []).find((item) => item.framework_id === (form.getFieldValue('framework_id') ?? 'ragas'))
  const selectedBatchId = Form.useWatch('batch_id', form)
  const completedChunkRuns = (chunkRuns.data ?? []).filter(
    (run: ChunkRun) => ['completed', 'completed_with_errors'].includes(run.status) && (!selectedBatchId || run.batch_id === selectedBatchId),
  )
  const llmOptions = (models.data ?? [])
    .filter((model) => model.enabled && model.model_category !== 'embedding')
    .map((model) => ({ value: model.model_id, label: `${model.display_name} (${model.model_category})` }))
  const embeddingOptions = (models.data ?? [])
    .filter((model) => model.enabled && model.model_category === 'embedding')
    .map((model) => ({ value: model.model_id, label: model.display_name }))

  useEffect(() => {
    const defaultEmbedding = defaults.data?.defaults.default_embedding_model
    if (defaultEmbedding && !form.getFieldValue('embedding_model_id')) {
      form.setFieldValue('embedding_model_id', defaultEmbedding)
    }
  }, [defaults.data, form])

  const submit = async () => {
    try {
      const values = await form.validateFields()
      const advanced = parseJson(values.advanced_config_text)
      const payload = {
        batch_id: values.batch_id,
        chunk_run_id: values.chunk_run_id,
        framework_id: values.framework_id,
        judge_llm_model_id: values.judge_llm_model_id,
        embedding_model_id: values.embedding_model_id,
        generator_config: {
          testset_size: values.testset_size,
          language: values.language,
          query_distribution: {
            single_hop_specific: Number(values.single_hop_specific ?? 0.7),
            multi_hop_specific: Number(values.multi_hop_specific ?? 0.2),
            multi_hop_abstract: Number(values.multi_hop_abstract ?? 0.1),
          },
          chunk_sampling: {
            mode: 'all_completed_chunks',
            max_chunks: values.max_chunks,
            min_char_count: values.min_char_count,
            max_char_count: values.max_char_count,
          },
          persona: values.persona ?? '',
          llm_context: values.llm_context ?? '',
          random_seed: values.random_seed,
          advanced_config: advanced,
        },
      }
      createRun.mutate(payload, { onSuccess: () => message.success('测评集任务已创建'), onError: (error) => message.error(error instanceof Error ? error.message : '创建失败') })
    } catch (error) {
      message.error(error instanceof Error ? error.message : '请检查配置')
    }
  }

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>测评集生成</Typography.Title>
        <Typography.Text type="secondary">批次用于筛选可选分块任务，测评集实际基于选中的 ChunkRun 及其 chunks 生成。</Typography.Text>
      </div>
      <Card title="创建任务">
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            framework_id: 'ragas',
            testset_size: 10,
            language: 'zh',
            single_hop_specific: 0.7,
            multi_hop_specific: 0.2,
            multi_hop_abstract: 0.1,
            advanced_config_text: '{}',
          }}
        >
          {framework?.availability_status !== 'available' && framework ? (
            <Alert
              type="warning"
              showIcon
              message={framework.availability_reason}
              description={framework.dependency_install_hint}
            />
          ) : null}
          <Form.Item name="framework_id" label="测评框架" rules={[{ required: true }]}>
            <Select options={(frameworks.data ?? []).map((item) => ({ value: item.framework_id, label: `${item.display_name} / ${item.availability_status}`, disabled: item.availability_status !== 'available' }))} />
          </Form.Item>
          <Form.Item name="batch_id" label="材料批次（筛选范围）" rules={[{ required: true }]}>
            <Select options={(batches.data ?? []).map((batch) => ({ value: batch.batch_id, label: batch.batch_name }))} />
          </Form.Item>
          <Form.Item name="chunk_run_id" label="分块任务（实际生成来源）" rules={[{ required: true }]}>
            <Select options={completedChunkRuns.map((run) => ({ value: run.run_id, label: `${run.chunker_name} / ${run.total_chunks} chunks / ${run.status}` }))} />
          </Form.Item>
          <Space wrap className="fullWidth">
            <Form.Item name="judge_llm_model_id" label="Judge LLM" rules={[{ required: true }]}><Select className="wideSelect" options={llmOptions} /></Form.Item>
            <Form.Item name="embedding_model_id" label="Embedding" rules={[{ required: true, message: '请选择 embedding 模型' }]}><Select className="wideSelect" options={embeddingOptions} /></Form.Item>
            <Form.Item name="testset_size" label="样本数"><InputNumber min={1} max={500} /></Form.Item>
            <Form.Item name="language" label="语言">
              <Select
                className="wideSelect"
                options={[
                  { value: 'zh', label: '中文 / zh' },
                  { value: 'en', label: 'English / en' },
                  { value: 'ja', label: '日本語 / ja' },
                  { value: 'ko', label: '한국어 / ko' },
                ]}
              />
            </Form.Item>
          </Space>
          <Collapse
            ghost
            items={[
              {
                key: 'advanced',
                label: '高级选项',
                children: (
                  <>
                    <Space wrap>
                      <Form.Item name="single_hop_specific" label="Single-hop"><InputNumber min={0} max={1} step={0.1} /></Form.Item>
                      <Form.Item name="multi_hop_specific" label="Multi-hop Specific"><InputNumber min={0} max={1} step={0.1} /></Form.Item>
                      <Form.Item name="multi_hop_abstract" label="Multi-hop Abstract"><InputNumber min={0} max={1} step={0.1} /></Form.Item>
                      <Form.Item name="max_chunks" label="最大 Chunk"><InputNumber min={1} /></Form.Item>
                      <Form.Item name="min_char_count" label="最小字符"><InputNumber min={0} /></Form.Item>
                      <Form.Item name="max_char_count" label="最大字符"><InputNumber min={1} /></Form.Item>
                      <Form.Item name="random_seed" label="Seed"><InputNumber /></Form.Item>
                    </Space>
                    <Form.Item name="persona" label="Persona"><Input /></Form.Item>
                    <Form.Item name="llm_context" label="业务背景"><Input.TextArea rows={3} /></Form.Item>
                    <Form.Item name="advanced_config_text" label="高级 JSON"><Input.TextArea rows={5} /></Form.Item>
                  </>
                ),
              },
            ]}
          />
          <Button type="primary" loading={createRun.isPending} onClick={submit}>创建测评集任务</Button>
        </Form>
      </Card>
    </Space>
  )
}
