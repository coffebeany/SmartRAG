import { App, Button, Card, Form, Input, Select, Space, Switch, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useEffect } from 'react'
import { useChunkStrategies, useParserStrategies, useProcessingDefaultRules, useUpdateProcessingDefaultRules } from '../api/hooks'
import type { ProcessingDefaultRule } from '../api/types'

const METADATA_OPTIONS = [
  { value: 'metadata.none', label: '不抽取 Metadata' },
  { value: 'metadata.basic', label: '基础 Metadata' },
  { value: 'metadata.document_structure', label: '文档结构 Metadata' },
]

export default function ProcessingRulesPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const rules = useProcessingDefaultRules()
  const parsers = useParserStrategies()
  const chunkers = useChunkStrategies()
  const updateRules = useUpdateProcessingDefaultRules()

  useEffect(() => {
    if (rules.data) {
      form.setFieldsValue({ rules: rules.data })
    }
  }, [form, rules.data])

  const columns: ColumnsType<ProcessingDefaultRule> = [
    { title: '后缀', dataIndex: 'file_ext', render: (value) => <Tag>{value}</Tag> },
    { title: 'Parser', dataIndex: 'parser_name' },
    { title: 'Chunker', dataIndex: 'chunker_plugin_id' },
    { title: 'Metadata', dataIndex: 'metadata_strategy_id' },
    { title: '启用', dataIndex: 'enabled', render: (value) => (value ? '是' : '否') },
  ]

  const parserOptionsForExt = (fileExt?: string) =>
    (parsers.data ?? [])
      .filter((parser) => !fileExt || parser.supported_file_exts.includes(fileExt))
      .map((parser) => ({ value: parser.parser_name, label: parser.display_name }))

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>默认处理规则</Typography.Title>
        <Typography.Text type="secondary">按后端已注册 parser 支持的文件后缀，配置默认 parser、chunker 和 metadata 策略。</Typography.Text>
      </div>
      <Card>
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => updateRules.mutate(values, { onSuccess: () => message.success('默认处理规则已保存') })}
        >
          <Form.List name="rules">
            {(fields) => (
              <Space direction="vertical" size={12} className="pageStack">
                {fields.map((field) => (
                  <div className="ruleGrid compactRuleGrid" key={field.key}>
                    <Form.Item name={[field.name, 'rule_id']} hidden><Input /></Form.Item>
                    <Form.Item shouldUpdate noStyle>
                      {() => {
                        const fileExt = form.getFieldValue(['rules', field.name, 'file_ext'])
                        return (
                          <>
                            <Form.Item name={[field.name, 'file_ext']} hidden><Input /></Form.Item>
                            <Form.Item label="后缀"><Tag className="ruleExtTag">{fileExt}</Tag></Form.Item>
                            <Form.Item name={[field.name, 'parser_name']} label="Parser" rules={[{ required: true }]}>
                              <Select options={parserOptionsForExt(fileExt)} />
                            </Form.Item>
                          </>
                        )
                      }}
                    </Form.Item>
                    <Form.Item name={[field.name, 'chunker_plugin_id']} label="Chunker">
                      <Select
                        options={(chunkers.data ?? []).map((chunker) => ({
                          value: chunker.chunker_name,
                          label: chunker.display_name,
                        }))}
                      />
                    </Form.Item>
                    <Form.Item name={[field.name, 'metadata_strategy_id']} label="Metadata"><Select options={METADATA_OPTIONS} /></Form.Item>
                    <Form.Item name={[field.name, 'enabled']} label="启用" valuePropName="checked"><Switch /></Form.Item>
                  </div>
                ))}
              </Space>
            )}
          </Form.List>
          <Button type="primary" htmlType="submit" loading={updateRules.isPending}>保存规则</Button>
        </Form>
      </Card>
      <Card title="当前已保存规则">
        <Table rowKey="rule_id" columns={columns} loading={rules.isLoading} dataSource={rules.data ?? []} />
      </Card>
    </Space>
  )
}
