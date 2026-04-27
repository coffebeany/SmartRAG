import { Alert, Button, Card, Col, Form, Input, InputNumber, Modal, Row, Select, Space, Switch, Table, Tag, Typography, App } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMemo, useState } from 'react'
import { useCreateModel, useModels, useProviders, useTestModel, useTestModelDraft, useTestModelDraftUpdate, useUpdateModel } from '../api/hooks'
import type { HealthCheckResult, ModelCategory, ModelConnection } from '../api/types'

interface ModelsPageProps {
  title?: string
  description?: string
  categoryFilter?: ModelCategory
}

export default function ModelsPage({
  title = '模型管理',
  description = '统一管理 LLM、Embedding、Reranker 和自定义模型服务。',
  categoryFilter,
}: ModelsPageProps) {
  const { message } = App.useApp()
  const [open, setOpen] = useState(false)
  const [editingModel, setEditingModel] = useState<ModelConnection | null>(null)
  const [testResult, setTestResult] = useState<HealthCheckResult | null>(null)
  const [testError, setTestError] = useState<string | null>(null)
  const [form] = Form.useForm()
  const models = useModels()
  const providers = useProviders()
  const createModel = useCreateModel()
  const updateModel = useUpdateModel()
  const testModel = useTestModel()
  const testModelDraft = useTestModelDraft()
  const testModelDraftUpdate = useTestModelDraftUpdate()

  const filteredModels = useMemo(
    () => (models.data ?? []).filter((model) => (categoryFilter ? model.model_category === categoryFilter : true)),
    [categoryFilter, models.data],
  )

  const columns: ColumnsType<ModelConnection> = useMemo(() => [
    { title: '名称', dataIndex: 'display_name' },
    { title: '类型', dataIndex: 'model_category', render: value => <Tag>{value}</Tag> },
    { title: 'Provider', dataIndex: 'provider' },
    { title: '模型名', dataIndex: 'model_name' },
    {
      title: '状态',
      dataIndex: 'connection_status',
      render: value => <Tag color={value === 'available' ? 'green' : value === 'failed' ? 'red' : 'default'}>{value}</Tag>,
    },
    { title: '能力', render: (_, record) => <Space wrap>{record.supports_streaming && <Tag>streaming</Tag>}{record.supports_tools && <Tag>tools</Tag>}{record.embedding_dimension && <Tag>{record.embedding_dimension}d</Tag>}</Space> },
    {
      title: '操作',
      render: (_, record) => (
        <Space>
          <Button onClick={() => openEdit(record)}>编辑</Button>
          <Button loading={testModel.isPending} onClick={() => testModel.mutate(record.model_id, { onSuccess: () => message.success('连接测试完成') })}>
            测试连接
          </Button>
        </Space>
      ),
    },
  ], [message, testModel])

  function defaultValues() {
    return {
      provider: 'openai_compatible',
      model_category: categoryFilter ?? 'llm',
      base_url: 'https://api.openai.com/v1',
      timeout_seconds: 30,
      max_retries: 2,
      enabled: true,
    }
  }

  function openCreate() {
    setEditingModel(null)
    setTestResult(null)
    setTestError(null)
    form.setFieldsValue(defaultValues())
    setOpen(true)
  }

  function openEdit(model: ModelConnection) {
    setEditingModel(model)
    setTestResult(null)
    setTestError(null)
    form.setFieldsValue({
      display_name: model.display_name,
      model_name: model.model_name,
      model_category: model.model_category,
      provider: model.provider,
      base_url: model.base_url,
      api_key: undefined,
      api_version: model.api_version,
      timeout_seconds: model.timeout_seconds,
      max_retries: model.max_retries,
      enabled: model.enabled,
      context_window: model.context_window,
      max_output_tokens: model.max_output_tokens,
      supports_streaming: model.supports_streaming,
      supports_json_schema: model.supports_json_schema,
      supports_tools: model.supports_tools,
      supports_vision: model.supports_vision,
      supports_batch: model.supports_batch,
      model_traits: model.model_traits,
      pricing: model.pricing,
    })
    setOpen(true)
  }

  function closeModal() {
    setOpen(false)
    setEditingModel(null)
    setTestResult(null)
    setTestError(null)
    form.resetFields()
  }

  function sanitizePayload(values: Record<string, unknown>) {
    const payload = { ...values }
    if (editingModel && !payload.api_key) {
      delete payload.api_key
    }
    return payload
  }

  async function handleTestInModal() {
    setTestResult(null)
    setTestError(null)
    try {
      const values = await form.validateFields()
      const result = editingModel
        ? await testModelDraftUpdate.mutateAsync({
            modelId: editingModel.model_id,
            payload: sanitizePayload(values),
          })
        : await testModelDraft.mutateAsync(values)
      setTestResult(result)
      if (result.status === 'available') {
        message.success('连接测试成功')
      } else {
        message.error('连接测试失败')
      }
    } catch (error) {
      const reason = error instanceof Error ? error.message : '连接测试失败'
      setTestError(reason)
    }
  }

  function handleFinish(values: Record<string, unknown>) {
    const payload = sanitizePayload(values)
    if (editingModel) {
      updateModel.mutate(
        { modelId: editingModel.model_id, payload },
        { onSuccess: () => { message.success('模型已更新'); closeModal() } },
      )
      return
    }
    createModel.mutate(payload, { onSuccess: () => { message.success('模型已保存'); closeModal() } })
  }

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <Row justify="space-between" align="middle">
        <Col>
          <Typography.Title level={3}>{title}</Typography.Title>
          <Typography.Text type="secondary">{description}</Typography.Text>
        </Col>
        <Col>
          <Button type="primary" onClick={openCreate}>新增模型</Button>
        </Col>
      </Row>
      <Card>
        <Table rowKey="model_id" loading={models.isLoading} columns={columns} dataSource={filteredModels} />
      </Card>
      <Modal
        title={editingModel ? '编辑模型' : '新增模型'}
        open={open}
        onCancel={closeModal}
        onOk={() => form.submit()}
        confirmLoading={createModel.isPending || updateModel.isPending}
        okText={editingModel ? '保存修改' : '保存模型'}
        width={720}
        footer={(_, { OkBtn, CancelBtn }) => (
          <Space>
            <Button loading={testModelDraft.isPending || testModelDraftUpdate.isPending} onClick={handleTestInModal}>
              测试连接
            </Button>
            <CancelBtn />
            <OkBtn />
          </Space>
        )}
      >
        {editingModel?.api_key_masked && (
          <Alert
            className="modalNotice"
            type="info"
            showIcon
            message={`当前密钥：${editingModel.api_key_masked}`}
            description="编辑时 API Key 留空会继续使用现有密钥；填写新值则会覆盖。"
          />
        )}
        {testResult && (
          <Alert
            className="modalNotice"
            type={testResult.status === 'available' ? 'success' : 'error'}
            showIcon
            message={testResult.status === 'available' ? '连接测试成功' : '连接测试失败'}
            description={
              <Space direction="vertical" size={4}>
                {typeof testResult.latency_ms === 'number' && <span>延迟：{testResult.latency_ms} ms</span>}
                {testResult.error && <span>原因：{testResult.error}</span>}
                {Object.keys(testResult.response_metadata ?? {}).length > 0 && (
                  <pre className="inlineTrace">{JSON.stringify(testResult.response_metadata, null, 2)}</pre>
                )}
              </Space>
            }
          />
        )}
        {testError && <Alert className="modalNotice" type="error" showIcon message="连接测试失败" description={testError} />}
        <Form
          form={form}
          layout="vertical"
          initialValues={defaultValues()}
          onFinish={handleFinish}
        >
          <Row gutter={16}>
            <Col span={12}><Form.Item name="display_name" label="显示名称" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="model_name" label="模型名" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="model_category" label="模型类型" rules={[{ required: true }]}><Select disabled={Boolean(categoryFilter)} options={['llm', 'embedding', 'reranker', 'multimodal', 'reasoning', 'custom'].map(value => ({ value, label: value }))} /></Form.Item></Col>
            <Col span={12}><Form.Item name="provider" label="Provider" rules={[{ required: true }]}><Select options={(providers.data ?? []).map(item => ({ value: item.provider, label: item.display_name }))} /></Form.Item></Col>
            <Col span={24}><Form.Item name="base_url" label="Base URL" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={24}><Form.Item name="api_key" label="API Key"><Input.Password /></Form.Item></Col>
            <Col span={8}><Form.Item name="timeout_seconds" label="超时秒数"><InputNumber className="fullWidth" min={1} max={300} /></Form.Item></Col>
            <Col span={8}><Form.Item name="max_retries" label="重试次数"><InputNumber className="fullWidth" min={0} max={10} /></Form.Item></Col>
            <Col span={8}><Form.Item name="enabled" label="启用" valuePropName="checked"><Switch /></Form.Item></Col>
          </Row>
        </Form>
      </Modal>
    </Space>
  )
}
