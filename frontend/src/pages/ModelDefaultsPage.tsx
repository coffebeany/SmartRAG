import { Button, Card, Form, Select, Space, Typography, App } from 'antd'
import { useEffect } from 'react'
import { useModelDefaults, useModels, useUpdateModelDefaults } from '../api/hooks'

const DEFAULT_KEYS = [
  'default_generation_llm',
  'default_reasoning_llm',
  'default_fast_llm',
  'default_judge_llm',
  'default_embedding_model',
  'default_reranker',
  'default_multimodal_model',
]

function categoriesForDefault(key: string) {
  if (key === 'default_embedding_model') return ['embedding']
  if (key === 'default_reranker') return ['reranker']
  if (key === 'default_multimodal_model') return ['multimodal', 'vision_embedding']
  return ['llm', 'reasoning', 'moe', 'custom']
}

export default function ModelDefaultsPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const models = useModels()
  const defaults = useModelDefaults()
  const updateDefaults = useUpdateModelDefaults()

  useEffect(() => {
    if (defaults.data) {
      form.setFieldsValue(defaults.data.defaults)
    }
  }, [defaults.data, form])

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>默认模型</Typography.Title>
        <Typography.Text type="secondary">项目级 fallback 模型，具体实验配置仍可覆盖。</Typography.Text>
      </div>
      <Card>
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => updateDefaults.mutate({ defaults: values }, { onSuccess: () => message.success('默认模型已保存') })}
        >
          {DEFAULT_KEYS.map(key => (
            <Form.Item key={key} name={key} label={key}>
              <Select
                allowClear
                options={(models.data ?? [])
                  .filter(item => categoriesForDefault(key).includes(item.model_category))
                  .map(item => ({ value: item.model_id, label: `${item.display_name} (${item.model_category})` }))}
              />
            </Form.Item>
          ))}
          <Button type="primary" htmlType="submit" loading={updateDefaults.isPending}>保存默认模型</Button>
        </Form>
      </Card>
    </Space>
  )
}
