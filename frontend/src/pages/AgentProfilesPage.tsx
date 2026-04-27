import { App, Button, Card, Col, Collapse, Form, Input, InputNumber, Modal, Row, Select, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useEffect, useMemo, useState } from 'react'
import { useAgentTypes, useAgents, useCreateAgent, useDryRunAgent, useDryRunAgentDraft, useModels, useUpdateAgent } from '../api/hooks'
import type { AgentProfile } from '../api/types'

const DEFAULT_DRY_RUN_INPUT = 'Hello,SmartRAG!'

interface DryRunResult {
  status?: string
  output?: unknown
  latency_ms?: number | null
  error?: string | null
  trace?: Record<string, unknown>
}

function PrettyJson({ value }: { value: unknown }) {
  return <pre className="jsonViewer">{JSON.stringify(value, null, 2)}</pre>
}

function DryRunResultView({ result }: { result: DryRunResult }) {
  return (
    <Space direction="vertical" size={12} className="pageStack dryRunResult">
      <Space wrap>
        <Tag color={result.status === 'available' ? 'green' : result.status === 'failed' ? 'red' : 'default'}>
          {result.status ?? 'unknown'}
        </Tag>
        {result.latency_ms != null && <Tag>{result.latency_ms} ms</Tag>}
      </Space>
      {result.error && (
        <Card size="small" title="Error">
          <Typography.Text type="danger">{result.error}</Typography.Text>
        </Card>
      )}
      <Card size="small" title="Output">
        {typeof result.output === 'string' ? (
          <Typography.Paragraph className="dryRunOutput">{result.output}</Typography.Paragraph>
        ) : (
          <PrettyJson value={result.output ?? null} />
        )}
      </Card>
      <Card size="small" title="Trace">
        <PrettyJson value={result.trace ?? {}} />
      </Card>
      <Card size="small" title="Raw JSON">
        <PrettyJson value={result} />
      </Card>
    </Space>
  )
}

function toFormValues(record: AgentProfile) {
  const runtime = record.runtime_config ?? {}
  return {
    agent_name: record.agent_name,
    agent_type: record.agent_type,
    model_id: record.model_id,
    prompt_template: record.prompt_template,
    temperature: Number(runtime.temperature ?? 0),
    max_output_tokens: Number(runtime.max_output_tokens ?? 2048),
    dry_run_input: DEFAULT_DRY_RUN_INPUT,
  }
}

function errorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message
  }
  return '请求失败'
}

export default function AgentProfilesPage() {
  const { message, modal } = App.useApp()
  const [open, setOpen] = useState(false)
  const [editingAgent, setEditingAgent] = useState<AgentProfile | null>(null)
  const [dryRunResult, setDryRunResult] = useState<DryRunResult | null>(null)
  const [form] = Form.useForm()
  const agents = useAgents()
  const models = useModels()
  const agentTypes = useAgentTypes()
  const createAgent = useCreateAgent()
  const updateAgent = useUpdateAgent()
  const dryRun = useDryRunAgent()
  const dryRunDraft = useDryRunAgentDraft()

  const applyDefaultPrompt = (agentType?: string) => {
    const selectedType = agentType ?? form.getFieldValue('agent_type')
    const selected = agentTypes.data?.find(item => item.agent_type === selectedType)
    if (selected) {
      form.setFieldValue('prompt_template', selected.default_prompt)
    }
  }

  const openCreate = () => {
    setEditingAgent(null)
    setDryRunResult(null)
    form.resetFields()
    form.setFieldsValue({
      agent_type: 'query_rewrite',
      temperature: 0,
      max_output_tokens: 2048,
      dry_run_input: DEFAULT_DRY_RUN_INPUT,
    })
    setOpen(true)
  }

  const openEdit = (record: AgentProfile) => {
    setEditingAgent(record)
    setDryRunResult(null)
    form.setFieldsValue(toFormValues(record))
    setOpen(true)
  }

  useEffect(() => {
    if (open && !editingAgent && agentTypes.data?.length && !form.getFieldValue('prompt_template')) {
      applyDefaultPrompt('query_rewrite')
    }
  }, [agentTypes.data, editingAgent, open])

  const submitPayload = (values: Record<string, unknown>) => ({
    agent_name: values.agent_name,
    agent_type: values.agent_type,
    model_id: values.model_id,
    prompt_template: values.prompt_template,
    runtime_config: {
      temperature: values.temperature ?? 0,
      max_output_tokens: values.max_output_tokens ?? 2048,
    },
  })

  const handleSave = (values: Record<string, unknown>) => {
    const payload = submitPayload(values)
    if (editingAgent) {
      updateAgent.mutate(
        { agentId: editingAgent.agent_id, payload },
        {
          onSuccess: () => {
            message.success('Agent 已更新')
            setOpen(false)
            form.resetFields()
          },
          onError: (error) => {
            message.error(`保存失败：${errorMessage(error)}`)
          },
        },
      )
      return
    }
    createAgent.mutate(payload, {
      onSuccess: () => {
        message.success('Agent 已保存')
        setOpen(false)
        form.resetFields()
      },
      onError: (error) => {
        message.error(`保存失败：${errorMessage(error)}`)
      },
    })
  }

  const handleDryRunInModal = async () => {
    setDryRunResult(null)
    const values = await form.validateFields(['model_id', 'prompt_template', 'temperature', 'max_output_tokens', 'dry_run_input'])
    dryRunDraft.mutate(
      {
        model_id: values.model_id,
        prompt_template: values.prompt_template,
        runtime_config: {
          temperature: values.temperature ?? 0,
          max_output_tokens: values.max_output_tokens ?? 2048,
        },
        input_text: values.dry_run_input || DEFAULT_DRY_RUN_INPUT,
      },
      {
        onSuccess: (result) => setDryRunResult(result as DryRunResult),
        onError: (error) => {
          setDryRunResult({
            status: 'failed',
            error: errorMessage(error),
            trace: { source: 'agent-profile-modal' },
          })
        },
      },
    )
  }

  const showDryRunResult = (result: DryRunResult) => {
    modal.info({
      title: 'Dry-run 结果',
      width: 760,
      content: <DryRunResultView result={result} />,
    })
  }

  const columns: ColumnsType<AgentProfile> = useMemo(() => [
    { title: '名称', dataIndex: 'agent_name' },
    { title: '类型', dataIndex: 'agent_type', render: value => <Tag>{value}</Tag> },
    { title: '模型', render: (_, record) => models.data?.find(item => item.model_id === record.model_id)?.display_name ?? record.model_id },
    { title: 'Dry-run', render: (_, record) => <Tag color={record.dry_run_status === 'available' ? 'green' : record.dry_run_status === 'failed' ? 'red' : 'default'}>{record.dry_run_status}</Tag> },
    {
      title: '操作',
      render: (_, record) => (
        <Space>
          <Button onClick={() => openEdit(record)}>编辑</Button>
          <Button
            loading={dryRun.isPending}
            onClick={() => dryRun.mutate(
              { agentId: record.agent_id, payload: { input_text: DEFAULT_DRY_RUN_INPUT } },
              {
                onSuccess: (result) => showDryRunResult(result as DryRunResult),
                onError: (error) => showDryRunResult({
                  status: 'failed',
                  error: errorMessage(error),
                  trace: { agent_id: record.agent_id, source: 'agent-profile-table' },
                }),
              },
            )}
          >
            Dry-run
          </Button>
        </Space>
      ),
    },
  ], [dryRun, models.data])

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <Row justify="space-between" align="middle">
        <Col>
          <Typography.Title level={3}>Agent Profile</Typography.Title>
          <Typography.Text type="secondary">把基础 LLM 封装为 query rewrite、HyDE、metadata extraction 等可复用能力。</Typography.Text>
        </Col>
        <Col><Button type="primary" onClick={openCreate}>新增 Agent</Button></Col>
      </Row>
      <Card>
        <Table rowKey="agent_id" loading={agents.isLoading} columns={columns} dataSource={agents.data ?? []} />
      </Card>
      <Modal
        title={editingAgent ? '编辑 Agent Profile' : '新增 Agent Profile'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createAgent.isPending || updateAgent.isPending}
        width={920}
        okText={editingAgent ? '保存修改' : '保存 Agent'}
      >
        <Form
          form={form}
          layout="vertical"
          onValuesChange={(changed) => {
            if (changed.agent_type && !editingAgent) {
              applyDefaultPrompt(changed.agent_type)
            }
          }}
          onFinish={handleSave}
        >
          <Row gutter={16}>
            <Col span={12}><Form.Item name="agent_name" label="Agent 名称" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="agent_type" label="Agent 类型" rules={[{ required: true }]}><Select options={(agentTypes.data ?? []).map(item => ({ value: item.agent_type, label: item.display_name }))} /></Form.Item></Col>
            <Col span={24}><Form.Item name="model_id" label="基础 LLM" rules={[{ required: true }]}><Select options={(models.data ?? []).filter(item => item.model_category !== 'embedding').map(item => ({ value: item.model_id, label: item.display_name }))} /></Form.Item></Col>
            <Col span={24}>
              <Form.Item
                name="prompt_template"
                label={<Space><span>Prompt</span><Button size="small" onClick={(event) => { event.preventDefault(); applyDefaultPrompt() }}>恢复默认</Button></Space>}
                rules={[{ required: true }]}
              >
                <Input.TextArea rows={10} />
              </Form.Item>
            </Col>
            <Col span={24}>
              <Collapse
                ghost
                items={[
                  {
                    key: 'advanced',
                    label: '高级选项',
                    children: (
                      <Row gutter={16}>
                        <Col span={12}><Form.Item name="temperature" label="Temperature"><InputNumber className="fullWidth" min={0} max={2} step={0.1} /></Form.Item></Col>
                        <Col span={12}><Form.Item name="max_output_tokens" label="Max output tokens"><InputNumber className="fullWidth" min={64} max={32768} /></Form.Item></Col>
                      </Row>
                    ),
                  },
                ]}
              />
            </Col>
            <Col span={24}>
              <Card size="small" title="Dry-run" className="dryRunPanel">
                <Form.Item name="dry_run_input" label="测试输入">
                  <Input.TextArea rows={3} />
                </Form.Item>
                <Button loading={dryRunDraft.isPending} onClick={handleDryRunInModal}>
                  在弹窗中 Dry-run
                </Button>
                {dryRunResult && <DryRunResultView result={dryRunResult} />}
              </Card>
            </Col>
          </Row>
        </Form>
      </Modal>
    </Space>
  )
}
