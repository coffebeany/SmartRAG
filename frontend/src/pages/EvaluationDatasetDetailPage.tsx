import { App, Button, Card, Collapse, Descriptions, Empty, Form, Input, Modal, Popconfirm, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  useCreateEvaluationDatasetItem,
  useDeleteEvaluationDatasetItem,
  useEvaluationDatasetItems,
  useEvaluationDatasetRun,
  useUpdateEvaluationDatasetItem,
} from '../api/hooks'
import type { EvaluationDatasetItem } from '../api/types'
import { TableActionButton } from '../components/TableActionButton'

function statusColor(status?: string) {
  if (status === 'completed') return 'green'
  if (status === 'failed') return 'red'
  if (status === 'running') return 'blue'
  return 'default'
}

function parseJsonArray(text?: string) {
  if (!text?.trim()) return []
  const value = JSON.parse(text)
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) {
    throw new Error('JSON 必须是字符串数组')
  }
  return value
}

function arrayText(value?: string[]) {
  return JSON.stringify(value ?? [], null, 2)
}

export default function EvaluationDatasetDetailPage() {
  const { message } = App.useApp()
  const { runId } = useParams()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [editingItem, setEditingItem] = useState<EvaluationDatasetItem | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()
  const run = useEvaluationDatasetRun(runId)
  const items = useEvaluationDatasetItems(runId, (page - 1) * pageSize, pageSize)
  const createItem = useCreateEvaluationDatasetItem(runId)
  const updateItem = useUpdateEvaluationDatasetItem(runId)
  const deleteItem = useDeleteEvaluationDatasetItem(runId)
  const editable = Boolean(run.data && !['pending', 'running'].includes(run.data.status))

  const openCreate = () => {
    setEditingItem(null)
    form.setFieldsValue({
      question: '',
      ground_truth: '',
      reference_contexts_text: '[]',
      source_chunk_ids_text: '[]',
      source_file_ids_text: '[]',
    })
    setModalOpen(true)
  }

  const openEdit = (item: EvaluationDatasetItem) => {
    setEditingItem(item)
    form.setFieldsValue({
      question: item.question,
      ground_truth: item.ground_truth,
      reference_contexts_text: arrayText(item.reference_contexts),
      source_chunk_ids_text: arrayText(item.source_chunk_ids),
      source_file_ids_text: arrayText(item.source_file_ids),
    })
    setModalOpen(true)
  }

  const submitItem = async () => {
    try {
      const values = await form.validateFields()
      const payload = {
        question: values.question,
        ground_truth: values.ground_truth,
        reference_contexts: parseJsonArray(values.reference_contexts_text),
        source_chunk_ids: parseJsonArray(values.source_chunk_ids_text),
        source_file_ids: parseJsonArray(values.source_file_ids_text),
        synthesizer_name: editingItem?.synthesizer_name ?? 'manual',
        item_metadata: editingItem?.item_metadata ?? { source: 'manual' },
      }
      if (editingItem) {
        updateItem.mutate(
          { itemId: editingItem.item_id, payload },
          {
            onSuccess: () => {
              message.success('样本已更新')
              setModalOpen(false)
            },
            onError: (error) => message.error(error instanceof Error ? error.message : '更新失败'),
          },
        )
      } else {
        createItem.mutate(payload, {
          onSuccess: () => {
            message.success('样本已新增')
            setModalOpen(false)
          },
          onError: (error) => message.error(error instanceof Error ? error.message : '新增失败'),
        })
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : '请检查样本内容')
    }
  }

  const columns: ColumnsType<EvaluationDatasetItem> = [
    { title: '问题', dataIndex: 'question', width: 320, render: (value) => <Typography.Paragraph ellipsis={{ rows: 3 }}>{value}</Typography.Paragraph> },
    { title: '标准答案', dataIndex: 'ground_truth', width: 360, render: (value) => <Typography.Paragraph ellipsis={{ rows: 3 }}>{value}</Typography.Paragraph> },
    { title: '来源 Chunk', dataIndex: 'source_chunk_ids', render: (value: string[]) => <Space wrap>{value.map((item) => <Tag key={item}>{item.slice(0, 8)}</Tag>)}</Space> },
    { title: '生成器', dataIndex: 'synthesizer_name', render: (value) => <Tag>{String(value ?? 'NA')}</Tag> },
    { title: '上下文数', dataIndex: 'reference_contexts', render: (value: string[]) => value.length },
    {
      title: '操作',
      width: 130,
      render: (_, record) => (
        <Space>
          <TableActionButton disabled={!editable} onClick={() => openEdit(record)}>编辑</TableActionButton>
          <Popconfirm
            title="删除样本"
            description="删除后该问题不会再参与后续测评报告。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => deleteItem.mutate(record.item_id, {
              onSuccess: () => message.success('样本已删除'),
              onError: (error) => message.error(error instanceof Error ? error.message : '删除失败'),
            })}
          >
            <TableActionButton danger disabled={!editable} loading={deleteItem.isPending}>删除</TableActionButton>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  if (!run.isLoading && !run.data) {
    return <Empty description="测评集不存在" />
  }

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>测评集详情</Typography.Title>
        <Typography.Text type="secondary">查看生成任务、实际配置、问题与标准答案。</Typography.Text>
      </div>
      {run.data && (
        <Card>
          <Descriptions column={2}>
            <Descriptions.Item label="任务">{run.data.display_name ?? run.data.run_id}</Descriptions.Item>
            <Descriptions.Item label="状态"><Tag color={statusColor(run.data.status)}>{run.data.status}</Tag></Descriptions.Item>
            <Descriptions.Item label="批次">{run.data.batch_name ?? run.data.batch_id}</Descriptions.Item>
            <Descriptions.Item label="ChunkRun">{run.data.chunk_run_id}</Descriptions.Item>
            <Descriptions.Item label="框架">{run.data.framework_id}</Descriptions.Item>
            <Descriptions.Item label="样本">{run.data.completed_items}/{run.data.total_items}</Descriptions.Item>
          </Descriptions>
          {run.data.error_summary ? <Typography.Text type="danger">{run.data.error_summary}</Typography.Text> : null}
        </Card>
      )}
      {run.data && (
        <Card title="生成配置">
          <pre className="jsonViewer">{JSON.stringify(run.data.generator_config, null, 2)}</pre>
        </Card>
      )}
      <Card
        title="问题与答案"
        extra={<Button type="primary" disabled={!editable} onClick={openCreate}>新增问题</Button>}
      >
        <Table
          rowKey="item_id"
          loading={items.isLoading}
          columns={columns}
          dataSource={items.data?.items ?? []}
          pagination={{
            current: page,
            pageSize,
            total: items.data?.total ?? 0,
            onChange: (nextPage, nextSize) => {
              setPage(nextPage)
              setPageSize(nextSize)
            },
          }}
        />
      </Card>
      <Modal
        title={editingItem ? '编辑测评样本' : '新增测评样本'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={submitItem}
        confirmLoading={createItem.isPending || updateItem.isPending}
        width={760}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="question" label="问题" rules={[{ required: true, message: '请输入问题' }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="ground_truth" label="标准答案" rules={[{ required: true, message: '请输入标准答案' }]}>
            <Input.TextArea rows={5} />
          </Form.Item>
          <Collapse
            ghost
            items={[
              {
                key: 'source',
                label: '来源与上下文 JSON',
                children: (
                  <>
                    <Form.Item name="reference_contexts_text" label="reference_contexts">
                      <Input.TextArea rows={5} />
                    </Form.Item>
                    <Form.Item name="source_chunk_ids_text" label="source_chunk_ids">
                      <Input.TextArea rows={3} />
                    </Form.Item>
                    <Form.Item name="source_file_ids_text" label="source_file_ids">
                      <Input.TextArea rows={3} />
                    </Form.Item>
                  </>
                ),
              },
            ]}
          />
        </Form>
      </Modal>
    </Space>
  )
}
