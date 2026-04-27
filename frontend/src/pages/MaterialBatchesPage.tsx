import { App, Button, Card, Col, Form, Input, Modal, Row, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useCreateMaterialBatch, useDeleteMaterialBatch, useMaterialBatches, useUpdateMaterialBatch } from '../api/hooks'
import type { MaterialBatch } from '../api/types'

export default function MaterialBatchesPage() {
  const { message } = App.useApp()
  const [open, setOpen] = useState(false)
  const [editingBatch, setEditingBatch] = useState<MaterialBatch | null>(null)
  const [deletingBatch, setDeletingBatch] = useState<MaterialBatch | null>(null)
  const [deleteText, setDeleteText] = useState('')
  const [form] = Form.useForm()
  const [editForm] = Form.useForm()
  const batches = useMaterialBatches()
  const createBatch = useCreateMaterialBatch()
  const updateBatch = useUpdateMaterialBatch()
  const deleteBatch = useDeleteMaterialBatch()
  const canConfirmDelete = deleteText.trim() === 'delete'

  const getErrorMessage = (error: unknown) => {
    if (error instanceof Error) return error.message
    return '删除失败，请稍后重试'
  }

  const columns: ColumnsType<MaterialBatch> = useMemo(
    () => [
      {
        title: '批次名称',
        dataIndex: 'batch_name',
        render: (value, record) => <Link to={`/config/materials/batches/${record.batch_id}`}>{value}</Link>,
      },
      { title: '版本', dataIndex: 'current_version', render: (value) => <Tag>v{value}</Tag> },
      { title: '文件数', dataIndex: 'file_count' },
      { title: '描述', dataIndex: 'description' },
      { title: '更新时间', dataIndex: 'updated_at', render: (value) => new Date(value).toLocaleString() },
      {
        title: '操作',
        render: (_, record) => (
          <Space>
            <Button
              onClick={() => {
                setEditingBatch(record)
                editForm.setFieldsValue({
                  batch_name: record.batch_name,
                  description: record.description,
                })
              }}
            >
              编辑
            </Button>
            <Button
              danger
              onClick={() => {
                setDeletingBatch(record)
                setDeleteText('')
              }}
            >
              删除
            </Button>
          </Space>
        ),
      },
    ],
    [editForm],
  )

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <Row justify="space-between" align="middle">
        <Col>
          <Typography.Title level={3}>批次管理</Typography.Title>
          <Typography.Text type="secondary">以批次管理原始材料，每次文件变化都会生成快照版本。</Typography.Text>
        </Col>
        <Col>
          <Button type="primary" onClick={() => setOpen(true)}>新建批次</Button>
        </Col>
      </Row>
      <Card>
        <Table rowKey="batch_id" loading={batches.isLoading} columns={columns} dataSource={batches.data ?? []} />
      </Card>
      <Modal
        title="新建材料批次"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createBatch.isPending}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => createBatch.mutate(values, {
            onSuccess: () => {
              message.success('批次已创建')
              setOpen(false)
              form.resetFields()
            },
          })}
        >
          <Form.Item name="batch_name" label="批次名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={4} />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        title="编辑材料批次"
        open={Boolean(editingBatch)}
        onCancel={() => setEditingBatch(null)}
        onOk={() => editForm.submit()}
        confirmLoading={updateBatch.isPending}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={(values) => {
            if (!editingBatch) return
            updateBatch.mutate(
              { batchId: editingBatch.batch_id, payload: values },
              {
                onSuccess: () => {
                  message.success('批次已更新')
                  setEditingBatch(null)
                  editForm.resetFields()
                },
              },
            )
          }}
        >
          <Form.Item name="batch_name" label="批次名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={4} />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        title="删除材料批次"
        open={Boolean(deletingBatch)}
        okText="确认删除"
        okButtonProps={{ danger: true, disabled: !canConfirmDelete }}
        confirmLoading={deleteBatch.isPending}
        onCancel={() => {
          if (!deleteBatch.isPending) {
            setDeletingBatch(null)
            setDeleteText('')
          }
        }}
        onOk={async () => {
          if (!deletingBatch) return
          try {
            await deleteBatch.mutateAsync(deletingBatch.batch_id)
            message.success('批次已删除')
            setDeletingBatch(null)
            setDeleteText('')
          } catch (error) {
            message.error(getErrorMessage(error))
          }
        }}
      >
        <Space direction="vertical" size={12} className="pageStack">
          <Typography.Text>
            删除后会同步删除该批次记录、版本记录和该批次独占的底层文件。若某个文件被其它批次复用，后端会保留该文件。
          </Typography.Text>
          <Typography.Text strong>{deletingBatch?.batch_name}</Typography.Text>
          <Input
            value={deleteText}
            onChange={(event) => setDeleteText(event.target.value)}
            placeholder="输入 delete 确认删除"
            disabled={deleteBatch.isPending}
          />
        </Space>
      </Modal>
    </Space>
  )
}
