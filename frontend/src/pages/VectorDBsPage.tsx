import { Button, Card, Descriptions, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useRefreshVectorDBs, useVectorDBs } from '../api/hooks'
import type { VectorDB } from '../api/types'

function statusColor(status: string) {
  if (status === 'available') return 'green'
  if (status === 'adapter_only') return 'blue'
  if (status === 'needs_config') return 'gold'
  return 'red'
}

export default function VectorDBsPage() {
  const vectordbs = useVectorDBs()
  const refresh = useRefreshVectorDBs()

  const columns: ColumnsType<VectorDB> = [
    { title: 'VectorDB', dataIndex: 'display_name' },
    { title: '类型', dataIndex: 'db_type' },
    {
      title: '状态',
      dataIndex: 'availability_status',
      render: (value, record) => (
        <Tooltip title={record.availability_reason}>
          <Tag color={statusColor(value)}>{value}</Tag>
        </Tooltip>
      ),
    },
    {
      title: '默认存储位置',
      dataIndex: 'default_storage_uri',
      render: (value) => value || 'NA',
    },
    {
      title: '能力',
      dataIndex: 'capabilities',
      render: (items: string[]) => (
        <Space wrap>
          {items.map((item) => (
            <Tag key={item}>{item}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '依赖',
      dataIndex: 'required_dependencies',
      render: (items: string[]) => (items.length ? items.join(', ') : 'NA'),
    },
  ]

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>VectorDB</Typography.Title>
        <Typography.Text type="secondary">
          管理向量数据库 adapter、默认存储位置、依赖状态和可测试策略配置。
        </Typography.Text>
      </div>
      <Card>
        <Space direction="vertical" size={16} className="fullWidth">
          <Button loading={refresh.isPending} onClick={() => refresh.mutate()}>
            刷新状态
          </Button>
          <Table
            rowKey="vectordb_name"
            loading={vectordbs.isLoading}
            columns={columns}
            dataSource={vectordbs.data ?? []}
            expandable={{
              expandedRowRender: (record) => (
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="说明">{record.description}</Descriptions.Item>
                  <Descriptions.Item label="默认配置">
                    <pre>{JSON.stringify(record.default_config, null, 2)}</pre>
                  </Descriptions.Item>
                  <Descriptions.Item label="高级选项">
                    <pre>{JSON.stringify(record.advanced_options_schema, null, 2)}</pre>
                  </Descriptions.Item>
                </Descriptions>
              ),
            }}
          />
        </Space>
      </Card>
    </Space>
  )
}
