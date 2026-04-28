import { App, Button, Card, Drawer, Form, Input, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMemo, useState } from 'react'
import {
  useAgents,
  useComponentConfigs,
  useCreateComponentConfig,
  useDeleteComponentConfig,
  useModels,
  useRagComponents,
  useUpdateComponentConfig,
} from '../api/hooks'
import type { ComponentConfig, RagComponent } from '../api/types'
import { SchemaFormItems } from '../components/SchemaFormItems'
import { TableActionButton } from '../components/TableActionButton'

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

function titleFor(nodeType: string) {
  if (nodeType === 'passage_reranker') return 'Reranker 配置'
  if (nodeType === 'passage_filter') return 'Filter 配置'
  return 'Compressor 配置'
}

function compactJson(value: Record<string, unknown>) {
  const entries = Object.entries(value ?? {}).filter(([, item]) => item !== undefined && item !== '')
  if (!entries.length) return 'NA'
  return entries.map(([key, item]) => `${key}: ${String(item)}`).join(' / ')
}

function stripEmpty(value: Record<string, unknown> | undefined) {
  return Object.fromEntries(Object.entries(value ?? {}).filter(([, item]) => item !== undefined && item !== ''))
}

function componentOption(component: RagComponent) {
  return {
    value: component.module_type,
    disabled: ['missing_dependency', 'adapter_only'].includes(component.availability_status),
    label: (
      <Space>
        <span>{component.display_name}</span>
        <Tag color={statusColor(component.availability_status)}>{component.availability_status}</Tag>
      </Space>
    ),
  }
}

export default function ComponentConfigsPage({ nodeType }: { nodeType: string }) {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const components = useRagComponents(nodeType)
  const configs = useComponentConfigs(nodeType)
  const models = useModels()
  const agents = useAgents()
  const createConfig = useCreateComponentConfig()
  const updateConfig = useUpdateComponentConfig()
  const deleteConfig = useDeleteComponentConfig()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<ComponentConfig | null>(null)
  const [moduleType, setModuleType] = useState<string>()
  const [advanced, setAdvanced] = useState(false)
  const [configJson, setConfigJson] = useState('{}')
  const [secretJson, setSecretJson] = useState('{}')

  const sortedComponents = useMemo(
    () => [...(components.data ?? [])].sort((a, b) => statusRank(a.availability_status) - statusRank(b.availability_status) || a.display_name.localeCompare(b.display_name)),
    [components.data],
  )
  const selectedComponent = sortedComponents.find((item) => item.module_type === moduleType)

  function setFormForComponent(component?: RagComponent, record?: ComponentConfig) {
    const config = record?.config ?? component?.default_config ?? {}
    form.setFieldsValue({
      module_type: record?.module_type ?? component?.module_type,
      display_name: record?.display_name ?? component?.display_name,
      config,
      secret_config: {},
    })
    setModuleType(record?.module_type ?? component?.module_type)
    setConfigJson(JSON.stringify(config, null, 2))
    setSecretJson('{}')
  }

  function showCreate() {
    const first = sortedComponents.find((item) => !['missing_dependency', 'adapter_only'].includes(item.availability_status)) ?? sortedComponents[0]
    setEditing(null)
    setAdvanced(false)
    form.resetFields()
    setFormForComponent(first)
    setOpen(true)
  }

  function showEdit(record: ComponentConfig) {
    const component = sortedComponents.find((item) => item.module_type === record.module_type)
    setEditing(record)
    setAdvanced(false)
    form.resetFields()
    setFormForComponent(component, record)
    setOpen(true)
  }

  async function save() {
    if (!selectedComponent) return
    try {
      let values = await form.validateFields()
      if (advanced) {
        values = {
          ...values,
          config: JSON.parse(configJson || '{}'),
          secret_config: JSON.parse(secretJson || '{}'),
        }
      }
      const secretConfig = stripEmpty(values.secret_config)
      const payload: Record<string, unknown> = {
        node_type: nodeType,
        module_type: selectedComponent.module_type,
        display_name: values.display_name,
        config: stripEmpty(values.config),
        enabled: true,
      }
      if (!editing || Object.keys(secretConfig).length) {
        payload.secret_config = secretConfig
      }
      if (editing) {
        updateConfig.mutate(
          { configId: editing.config_id, payload },
          {
            onSuccess: () => {
              message.success('组件配置已更新')
              setOpen(false)
            },
            onError: (error) => message.error(error instanceof Error ? error.message : '保存失败'),
          },
        )
      } else {
        createConfig.mutate(payload, {
          onSuccess: () => {
            message.success('组件配置已创建')
            setOpen(false)
          },
          onError: (error) => message.error(error instanceof Error ? error.message : '保存失败'),
        })
      }
    } catch (error) {
      if (error instanceof SyntaxError) {
        message.error('高级 JSON 格式不正确')
      }
    }
  }

  const columns: ColumnsType<ComponentConfig> = [
    { title: '名称', dataIndex: 'display_name' },
    { title: '模块', dataIndex: 'module_type', render: (value) => <Typography.Text code>{value}</Typography.Text> },
    {
      title: '状态',
      dataIndex: 'availability_status',
      render: (value, record) => (
        <Tooltip title={record.availability_reason}>
          <Tag color={statusColor(value)}>{value}</Tag>
        </Tooltip>
      ),
    },
    { title: '配置摘要', dataIndex: 'config', render: (value) => compactJson(value ?? {}) },
    {
      title: '密钥',
      dataIndex: 'secret_config_masked',
      render: (value) => (Object.keys(value ?? {}).length ? compactJson(value) : 'NA'),
    },
    {
      title: '操作',
      render: (_, record) => (
        <Space>
          <TableActionButton onClick={() => showEdit(record)}>编辑</TableActionButton>
          <TableActionButton danger onClick={() => deleteConfig.mutate(record.config_id)}>删除</TableActionButton>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div className="pageHeader">
        <div>
          <Typography.Title level={3}>{titleFor(nodeType)}</Typography.Title>
          <Typography.Text type="secondary">管理可复用组件配置，展示依赖、密钥和当前可用状态。</Typography.Text>
        </div>
        <Button type="primary" onClick={showCreate}>新增配置</Button>
      </div>
      <Card title="已注册组件">
        <Table
          rowKey="module_type"
          loading={components.isLoading}
          dataSource={sortedComponents}
          columns={[
            { title: '模块', dataIndex: 'module_type', render: (value) => <Typography.Text code>{value}</Typography.Text> },
            { title: '显示名称', dataIndex: 'display_name' },
            {
              title: '状态',
              dataIndex: 'availability_status',
              render: (value, record) => (
                <Tooltip title={record.availability_reason}>
                  <Tag color={statusColor(value)}>{value}</Tag>
                </Tooltip>
              ),
            },
            { title: '依赖', dataIndex: 'required_dependencies', render: (items: string[]) => (items.length ? items.join(', ') : 'NA') },
            { title: '安装提示', dataIndex: 'dependency_install_hint', render: (value) => value ? <Typography.Text code>{value}</Typography.Text> : 'NA' },
          ]}
        />
      </Card>
      <Card title="组件配置">
        <Table rowKey="config_id" loading={configs.isLoading} columns={columns} dataSource={configs.data ?? []} />
      </Card>
      <Drawer
        title={editing ? '编辑组件配置' : '新增组件配置'}
        open={open}
        onClose={() => setOpen(false)}
        width={520}
        extra={<Button type="primary" loading={createConfig.isPending || updateConfig.isPending} onClick={save}>保存</Button>}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="module_type" label="模块" rules={[{ required: true }]}>
            <Select
              disabled={Boolean(editing)}
              options={sortedComponents.map(componentOption)}
              onChange={(value) => {
                const component = sortedComponents.find((item) => item.module_type === value)
                setFormForComponent(component)
              }}
            />
          </Form.Item>
          <Form.Item name="display_name" label="配置名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          {selectedComponent && (
            <Space direction="vertical" size={10} className="fullWidth">
              <Typography.Paragraph type="secondary">{selectedComponent.description}</Typography.Paragraph>
              <Button size="small" onClick={() => setAdvanced((value) => !value)}>
                {advanced ? '使用表单配置' : '高级 JSON'}
              </Button>
              {!advanced ? (
                <>
                  <SchemaFormItems schema={selectedComponent.config_schema} prefix="config" models={models.data} agents={agents.data} />
                  <SchemaFormItems
                    schema={selectedComponent.secret_config_schema}
                    prefix="secret_config"
                    models={models.data}
                    agents={agents.data}
                    preserveSecret={Boolean(editing)}
                  />
                </>
              ) : (
                <>
                  <Form.Item label="普通配置 JSON">
                    <Input.TextArea rows={8} value={configJson} onChange={(event) => setConfigJson(event.target.value)} />
                  </Form.Item>
                  <Form.Item label="密钥配置 JSON">
                    <Input.TextArea rows={4} value={secretJson} onChange={(event) => setSecretJson(event.target.value)} />
                  </Form.Item>
                </>
              )}
            </Space>
          )}
        </Form>
      </Drawer>
    </Space>
  )
}
