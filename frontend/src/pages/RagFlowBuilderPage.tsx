import { Alert, App, Button, Card, Form, Input, Select, Space, Tag, Tooltip, Typography } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAgents, useComponentConfigs, useCreateRagFlow, useModels, useRagComponents, useRagFlows, useUpdateRagFlow, useVectorRuns } from '../api/hooks'
import type { AgentProfile, ModelConnection, RagComponent, RagFlowNode } from '../api/types'
import { SchemaFormItems } from '../components/SchemaFormItems'

const NODE_TYPES = [
  { value: 'query_expansion', label: 'Query Expansion' },
  { value: 'passage_augmenter', label: 'Passage Augmenter' },
  { value: 'passage_reranker', label: 'Passage Rerank' },
  { value: 'passage_filter', label: 'Passage Filter' },
  { value: 'passage_compressor', label: 'Passage Compressor' },
]

const DEFAULT_RETRIEVAL_NODE: RagFlowNode = {
  node_type: 'retrieval',
  module_type: 'vectordb',
  config: { top_k: 5 },
  enabled: true,
}

function statusColor(status: string) {
  if (status === 'available') return 'green'
  if (status === 'needs_config') return 'gold'
  if (status === 'adapter_only') return 'blue'
  if (status === 'missing_env') return 'orange'
  return 'red'
}

function statusRank(status: string) {
  return ({ available: 0, needs_config: 1, missing_env: 2, missing_dependency: 3, adapter_only: 4 } as Record<string, number>)[status] ?? 9
}

function nodeLabel(type: string) {
  return NODE_TYPES.find((item) => item.value === type)?.label ?? type
}

function stripEmpty(value: Record<string, unknown> | undefined) {
  return Object.fromEntries(Object.entries(value ?? {}).filter(([, item]) => item !== undefined && item !== ''))
}

function hasLLMChoice(models: ModelConnection[] | undefined, agents: AgentProfile[] | undefined) {
  return Boolean((models ?? []).some((model) => model.enabled && model.model_category !== 'embedding') || (agents ?? []).some((agent) => agent.enabled))
}

function isSelectable(component: RagComponent, models: ModelConnection[] | undefined, agents: AgentProfile[] | undefined) {
  if (['missing_dependency', 'adapter_only'].includes(component.availability_status)) return false
  if (component.requires_llm && !hasLLMChoice(models, agents)) return false
  return true
}

function moduleOption(component: RagComponent, models: ModelConnection[] | undefined, agents: AgentProfile[] | undefined) {
  const disabled = !isSelectable(component, models, agents)
  const reason = component.requires_llm && !hasLLMChoice(models, agents) ? '需要先配置 LLM 或 Agent' : component.availability_reason
  return {
    value: component.module_type,
    disabled,
    label: (
      <Tooltip title={reason}>
        <Space>
          <span>{component.display_name}</span>
          <Tag color={statusColor(component.availability_status)}>{component.availability_status}</Tag>
        </Space>
      </Tooltip>
    ),
  }
}

function NodeConfigForm({
  node,
  component,
  models,
  agents,
  onChange,
}: {
  node: RagFlowNode
  component?: RagComponent
  models?: ModelConnection[]
  agents?: AgentProfile[]
  onChange: (config: Record<string, unknown>) => void
}) {
  const [form] = Form.useForm()
  const [advanced, setAdvanced] = useState(false)
  const [jsonText, setJsonText] = useState(JSON.stringify(node.config ?? {}, null, 2))
  const [jsonError, setJsonError] = useState<string | null>(null)

  useEffect(() => {
    form.setFieldsValue({ config: node.config ?? {} })
    setJsonText(JSON.stringify(node.config ?? {}, null, 2))
    setJsonError(null)
  }, [component?.module_type, form, node.config])

  if (!component) return null

  return (
    <Space direction="vertical" className="fullWidth">
      <Button size="small" onClick={() => setAdvanced((value) => !value)}>
        {advanced ? '使用表单配置' : '高级 JSON'}
      </Button>
      {!advanced ? (
        <Form
          form={form}
          layout="vertical"
          onValuesChange={(_, values) => onChange(stripEmpty(values.config))}
        >
          <SchemaFormItems schema={component.config_schema} prefix="config" models={models} agents={agents} />
        </Form>
      ) : (
        <>
          <Input.TextArea
            rows={5}
            value={jsonText}
            onChange={(event) => {
              const value = event.target.value
              setJsonText(value)
              try {
                onChange(JSON.parse(value || '{}'))
                setJsonError(null)
              } catch {
                setJsonError('JSON 格式不正确，修正后才会更新节点配置。')
              }
            }}
          />
          {jsonError && <Alert type="error" showIcon message={jsonError} />}
        </>
      )}
    </Space>
  )
}

export default function RagFlowBuilderPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const { flowId } = useParams()
  const isEditMode = Boolean(flowId)
  const vectorRuns = useVectorRuns()
  const components = useRagComponents()
  const componentConfigs = useComponentConfigs()
  const models = useModels()
  const agents = useAgents()
  const flows = useRagFlows()
  const createFlow = useCreateRagFlow()
  const updateFlow = useUpdateRagFlow()
  const [flowName, setFlowName] = useState('')
  const [description, setDescription] = useState('')
  const [vectorRunId, setVectorRunId] = useState<string>()
  const [retrievalNode, setRetrievalNode] = useState<RagFlowNode>(DEFAULT_RETRIEVAL_NODE)
  const [nodes, setNodes] = useState<RagFlowNode[]>([])
  const [loadedFlowId, setLoadedFlowId] = useState<string | null>(null)

  const completedVectorRuns = (vectorRuns.data ?? []).filter((run) => ['completed', 'completed_with_errors'].includes(run.status))
  const editingFlow = (flows.data ?? []).find((flow) => flow.flow_id === flowId)

  const componentsByNode = useMemo(() => {
    const grouped: Record<string, RagComponent[]> = {}
    ;(components.data ?? []).forEach((item) => {
      grouped[item.node_type] = grouped[item.node_type] ?? []
      grouped[item.node_type].push(item)
    })
    Object.values(grouped).forEach((items) => items.sort((a, b) => statusRank(a.availability_status) - statusRank(b.availability_status) || a.display_name.localeCompare(b.display_name)))
    return grouped
  }, [components.data])

  useEffect(() => {
    if (!flowId || !editingFlow || loadedFlowId === flowId) return
    const existingRetrievalNode = editingFlow.nodes.find((node) => node.node_type === 'retrieval') ?? {
      ...DEFAULT_RETRIEVAL_NODE,
      config: { top_k: editingFlow.retrieval_config?.top_k ?? 5 },
    }

    setFlowName(editingFlow.flow_name)
    setDescription(editingFlow.description ?? '')
    setVectorRunId(editingFlow.vector_run_id)
    setRetrievalNode(existingRetrievalNode)
    setNodes(editingFlow.nodes.filter((node) => node.node_type !== 'retrieval'))
    setLoadedFlowId(flowId)
  }, [editingFlow, flowId, loadedFlowId])

  const firstSelectableModule = (nodeType: string) => {
    const modules = componentsByNode[nodeType] ?? []
    return modules.find((item) => isSelectable(item, models.data, agents.data)) ?? modules[0]
  }

  const addNode = () => {
    const firstType = 'query_expansion'
    const firstModule = firstSelectableModule(firstType)
    setNodes((prev) => [
      ...prev,
      {
        node_type: firstType,
        module_type: firstModule?.module_type ?? 'pass_query_expansion',
        config: firstModule?.default_config ?? {},
        enabled: true,
      },
    ])
  }

  const updateNode = (index: number, patch: Partial<RagFlowNode>) => {
    setNodes((prev) => prev.map((node, nodeIndex) => (nodeIndex === index ? { ...node, ...patch } : node)))
  }

  const updateRetrievalNode = (patch: Partial<RagFlowNode>) => {
    setRetrievalNode((prev) => ({ ...prev, ...patch }))
  }

  const validateNodes = () => {
    for (const node of nodes.filter((item) => item.enabled)) {
      const component = components.data?.find((item) => item.node_type === node.node_type && item.module_type === node.module_type)
      if (!component) return `未知节点：${node.node_type}/${node.module_type}`
      if (!isSelectable(component, models.data, agents.data)) return `${component.display_name} 当前不可用：${component.availability_reason}`
      if (component.requires_llm && !node.config.model_id && !node.config.agent_id) return `${component.display_name} 需要选择 LLM 或 Agent`
      if (component.requires_api_key && !node.component_config_id) return `${component.display_name} 需要选择组件配置以提供 API key`
    }
    const retrievalComponent = components.data?.find((item) => item.node_type === retrievalNode.node_type && item.module_type === retrievalNode.module_type)
    if (!retrievalComponent) return `未知检索策略：${retrievalNode.module_type}`
    if (!isSelectable(retrievalComponent, models.data, agents.data)) return `${retrievalComponent.display_name} 当前不可用：${retrievalComponent.availability_reason}`
    return null
  }

  const save = () => {
    if (!flowName || !vectorRunId) {
      message.error('请填写流程名称并选择向量化任务')
      return
    }
    const error = validateNodes()
    if (error) {
      message.error(error)
      return
    }
    const payload = {
      flow_name: flowName,
      description,
      vector_run_id: vectorRunId,
      retrieval_config: { top_k: Number(retrievalNode.config.top_k ?? 5) },
      nodes: [
        ...nodes.filter((node) => node.node_type === 'query_expansion'),
        retrievalNode,
        ...nodes.filter((node) => node.node_type !== 'query_expansion'),
      ],
      enabled: true,
    }
    const options = {
      onSuccess: () => {
        message.success(isEditMode ? '流程已更新' : '流程已保存')
        navigate('/build/rag-flows')
      },
      onError: (error: unknown) => message.error(error instanceof Error ? error.message : isEditMode ? '更新失败' : '保存失败'),
    }
    if (isEditMode && flowId) {
      updateFlow.mutate({ flowId, payload }, options)
    } else {
      createFlow.mutate(payload, options)
    }
  }

  if (isEditMode && !flows.isLoading && !editingFlow) {
    return (
      <Space direction="vertical" size={16} className="pageStack">
        <Alert type="error" showIcon message="流程不存在或已删除" />
        <Button onClick={() => navigate('/build/rag-flows')}>返回流程列表</Button>
      </Space>
    )
  }

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>{isEditMode ? '编辑流程' : '流程构建'}</Typography.Title>
        <Typography.Text type="secondary">基于已完成向量化任务组合 Query Expansion、Retrieval 与检索后处理节点。</Typography.Text>
      </div>
      <Card>
        <Form layout="vertical">
          <Form.Item label="流程名称">
            <Input value={flowName} onChange={(event) => setFlowName(event.target.value)} />
          </Form.Item>
          <Form.Item label="说明">
            <Input value={description} onChange={(event) => setDescription(event.target.value)} />
          </Form.Item>
          <Form.Item label="向量化任务">
            <Select
              placeholder="选择已完成 VectorRun"
              value={vectorRunId}
              onChange={setVectorRunId}
              options={completedVectorRuns.map((run) => ({
                value: run.run_id,
                label: `${run.batch_name ?? run.batch_id} / ${run.vectordb_name} / ${run.total_vectors} vectors`,
              }))}
            />
          </Form.Item>
        </Form>
      </Card>
      <Card title="Retrieval 节点">
        {(() => {
          const modules = componentsByNode.retrieval ?? []
          const selectedComponent = modules.find((item) => item.module_type === retrievalNode.module_type)
          return (
            <Space direction="vertical" className="fullWidth">
              <Space wrap>
                <Select className="nodeSelect" value="retrieval" disabled options={[{ value: 'retrieval', label: 'Retrieval' }]} />
                <Select
                  className="nodeSelect"
                  value={retrievalNode.module_type}
                  options={modules.map((item) => moduleOption(item, models.data, agents.data))}
                  onChange={(value) => {
                    const next = modules.find((item) => item.module_type === value)
                    updateRetrievalNode({ module_type: value, config: next?.default_config ?? { top_k: 5 }, component_config_id: null })
                  }}
                />
              </Space>
              <NodeConfigForm
                node={retrievalNode}
                component={selectedComponent}
                models={models.data}
                agents={agents.data}
                onChange={(config) => updateRetrievalNode({ config })}
              />
            </Space>
          )
        })()}
      </Card>
      <Card title="节点配置" extra={<Button onClick={addNode}>添加节点</Button>}>
        <Space direction="vertical" size={12} className="fullWidth">
          {nodes.map((node, index) => {
            const modules = componentsByNode[node.node_type] ?? []
            const selectedComponent = modules.find((item) => item.module_type === node.module_type)
            const configs = (componentConfigs.data ?? [])
              .filter((item) => item.node_type === node.node_type && item.module_type === node.module_type)
              .sort((a, b) => statusRank(a.availability_status) - statusRank(b.availability_status) || a.display_name.localeCompare(b.display_name))
            return (
              <Card size="small" key={`${index}-${node.node_type}-${node.module_type}`}>
                <Space direction="vertical" className="fullWidth">
                  <Space wrap>
                    <Select
                      className="nodeSelect"
                      value={node.node_type}
                      options={NODE_TYPES}
                      onChange={(value) => {
                        const nextModule = firstSelectableModule(value)
                        updateNode(index, {
                          node_type: value,
                          module_type: nextModule?.module_type ?? '',
                          config: nextModule?.default_config ?? {},
                          component_config_id: null,
                        })
                      }}
                    />
                    <Select
                      className="nodeSelect"
                      value={node.module_type}
                      options={modules.map((item) => moduleOption(item, models.data, agents.data))}
                      onChange={(value) => {
                        const next = modules.find((item) => item.module_type === value)
                        updateNode(index, { module_type: value, config: next?.default_config ?? {}, component_config_id: null })
                      }}
                    />
                    {['passage_reranker', 'passage_filter', 'passage_compressor'].includes(node.node_type) && (
                      <Select
                        allowClear
                        className="nodeSelect"
                        placeholder="选择组件配置"
                        value={node.component_config_id ?? undefined}
                        options={configs.map((item) => ({
                          value: item.config_id,
                          disabled: item.availability_status !== 'available',
                          label: (
                            <Space>
                              <span>{item.display_name}</span>
                              <Tag color={statusColor(item.availability_status)}>{item.availability_status}</Tag>
                            </Space>
                          ),
                        }))}
                        onChange={(value) => updateNode(index, { component_config_id: value ?? null })}
                      />
                    )}
                    <Button onClick={() => setNodes((prev) => prev.filter((_, nodeIndex) => nodeIndex !== index))}>删除</Button>
                  </Space>
                  {selectedComponent?.requires_llm && !hasLLMChoice(models.data, agents.data) && <Alert type="warning" showIcon message="需要先在设置中配置可用 LLM 或 Agent Profile。" />}
                  {selectedComponent?.requires_api_key && !node.component_config_id && <Alert type="warning" showIcon message="该模块需要在组件配置中保存 API key，并在这里选择对应配置。" />}
                  <NodeConfigForm
                    node={node}
                    component={selectedComponent}
                    models={models.data}
                    agents={agents.data}
                    onChange={(config) => updateNode(index, { config })}
                  />
                </Space>
              </Card>
            )
          })}
        </Space>
      </Card>
      <Card title="流程图">
        <div className="flowGraph">
          {nodes.filter((node) => node.node_type === 'query_expansion').map((node, index) => (
            <div className="flowNode" key={`pre-${index}`}>
              <strong>{nodeLabel(node.node_type)}</strong>
              <span>{node.module_type}</span>
            </div>
          ))}
          <div className="flowNode retrieval">
            <strong>Retrieval</strong>
            <span>{retrievalNode.module_type} top_{String(retrievalNode.config.top_k ?? 5)}</span>
          </div>
          {nodes.filter((node) => node.node_type !== 'query_expansion').map((node, index) => (
            <div className="flowNode" key={`post-${index}`}>
              <strong>{nodeLabel(node.node_type)}</strong>
              <span>{node.module_type}</span>
            </div>
          ))}
          {!nodes.length && <Tag>Retrieval only</Tag>}
        </div>
      </Card>
      <Button type="primary" loading={createFlow.isPending || updateFlow.isPending} onClick={save}>
        {isEditMode ? '更新流程' : '保存流程'}
      </Button>
    </Space>
  )
}
