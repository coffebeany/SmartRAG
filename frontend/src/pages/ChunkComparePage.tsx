import { Card, Form, Select, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'
import { useChunkRunCompare, useMaterialBatches } from '../api/hooks'
import type { ChunkRunCompare } from '../api/types'

export default function ChunkComparePage() {
  const batches = useMaterialBatches()
  const firstBatchId = batches.data?.[0]?.batch_id
  const [form] = Form.useForm()
  const batchId = Form.useWatch('batch_id', form) ?? firstBatchId
  const compare = useChunkRunCompare(batchId)

  const columns: ColumnsType<ChunkRunCompare> = [
    {
      title: '任务',
      dataIndex: 'run_id',
      render: (value) => <Link to={`/build/chunk-runs/${value}`}>{value.slice(0, 8)}</Link>,
    },
    { title: '工具', dataIndex: 'chunker_name' },
    { title: '状态', dataIndex: 'status', render: (value) => <Tag>{value}</Tag> },
    { title: '文件', render: (_, record) => `${record.completed_files}/${record.total_files}` },
    { title: '失败', dataIndex: 'failed_files' },
    { title: 'Chunks', dataIndex: 'total_chunks' },
    { title: '平均长度', render: (_, record) => String(record.stats.avg_char_count ?? '-') },
    { title: '最小长度', render: (_, record) => String(record.stats.min_char_count ?? '-') },
    { title: '最大长度', render: (_, record) => String(record.stats.max_char_count ?? '-') },
    {
      title: '配置摘要',
      render: (_, record) => <Typography.Text code>{JSON.stringify(record.chunker_config).slice(0, 120)}</Typography.Text>,
    },
  ]

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>分块结果对比</Typography.Title>
        <Typography.Text type="secondary">按材料批次横向比较不同分块策略的结果统计。</Typography.Text>
      </div>
      <Card>
        <Form form={form} layout="vertical" initialValues={{ batch_id: firstBatchId }}>
          <Form.Item name="batch_id" label="材料批次">
            <Select
              placeholder="选择材料批次"
              options={(batches.data ?? []).map((batch) => ({
                value: batch.batch_id,
                label: `${batch.batch_name} (${batch.file_count} files)`,
              }))}
            />
          </Form.Item>
        </Form>
      </Card>
      <Card>
        <Table rowKey="run_id" loading={compare.isLoading} columns={columns} dataSource={compare.data ?? []} />
      </Card>
    </Space>
  )
}
