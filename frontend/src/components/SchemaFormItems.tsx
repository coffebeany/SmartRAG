import { Form, Input, InputNumber, Select, Switch, Typography } from 'antd'
import type { AgentProfile, ModelConnection } from '../api/types'

interface SchemaField {
  type?: string
  title?: string
  description?: string
  enum?: string[]
  minimum?: number
  maximum?: number
  secret?: boolean
}

interface ObjectSchema {
  properties?: Record<string, SchemaField>
  required?: string[]
}

interface SchemaFormItemsProps {
  schema?: Record<string, unknown>
  prefix: string
  models?: ModelConnection[]
  agents?: AgentProfile[]
  preserveSecret?: boolean
}

function objectSchema(schema?: Record<string, unknown>): ObjectSchema {
  return (schema ?? {}) as ObjectSchema
}

function labelFor(key: string, field: SchemaField) {
  return field.title ?? key
}

function modelOptions(models: ModelConnection[] | undefined, category: 'llm' | 'embedding') {
  return (models ?? [])
    .filter((model) => (category === 'llm' ? model.model_category !== 'embedding' : model.model_category === 'embedding'))
    .filter((model) => model.enabled)
    .map((model) => ({ value: model.model_id, label: `${model.display_name} (${model.model_name})` }))
}

function agentOptions(agents: AgentProfile[] | undefined) {
  return (agents ?? [])
    .filter((agent) => agent.enabled)
    .map((agent) => ({ value: agent.agent_id, label: agent.agent_name }))
}

export function SchemaFormItems({ schema, prefix, models, agents, preserveSecret = false }: SchemaFormItemsProps) {
  const parsed = objectSchema(schema)
  const required = new Set(parsed.required ?? [])
  const entries = Object.entries(parsed.properties ?? {})

  if (!entries.length) {
    return <Typography.Text type="secondary">该模块无需额外配置。</Typography.Text>
  }

  return (
    <>
      {entries.map(([key, field]) => {
        const isPreservedSecret = preserveSecret && field.secret
        const rules = required.has(key) && !isPreservedSecret ? [{ required: true, message: `请填写${labelFor(key, field)}` }] : undefined
        const name = [prefix, key]
        const help = field.description
        let input = <Input placeholder={String(labelFor(key, field))} />

        if (key === 'model_id') {
          input = <Select allowClear showSearch optionFilterProp="label" placeholder="选择已有 LLM" options={modelOptions(models, 'llm')} />
        } else if (key === 'embedding_model_id') {
          input = <Select allowClear showSearch optionFilterProp="label" placeholder="选择已有 Embedding 模型" options={modelOptions(models, 'embedding')} />
        } else if (key === 'agent_id') {
          input = <Select allowClear showSearch optionFilterProp="label" placeholder="选择已有 Agent Profile" options={agentOptions(agents)} />
        } else if (field.secret) {
          input = <Input.Password placeholder="留空表示不更新已有密钥" />
        } else if (field.enum?.length) {
          input = <Select options={field.enum.map((item) => ({ value: item, label: item }))} />
        } else if (field.type === 'integer' || field.type === 'number') {
          input = <InputNumber className="fullWidth" min={field.minimum} max={field.maximum} />
        } else if (field.type === 'boolean') {
          input = <Switch />
        }

        return (
          <Form.Item key={`${prefix}-${key}`} name={name} label={labelFor(key, field)} rules={rules} tooltip={help} valuePropName={field.type === 'boolean' ? 'checked' : 'value'}>
            {input}
          </Form.Item>
        )
      })}
    </>
  )
}

export function schemaDefaults(schema?: Record<string, unknown>) {
  const parsed = objectSchema(schema)
  return Object.fromEntries(
    Object.entries(parsed.properties ?? {}).map(([key, field]) => {
      if (field.type === 'boolean') return [key, false]
      return [key, undefined]
    }),
  )
}
