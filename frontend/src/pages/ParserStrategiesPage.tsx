import { Card, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useParserStrategies } from '../api/hooks'
import type { ParserStrategy } from '../api/types'

export default function ParserStrategiesPage() {
  const parsers = useParserStrategies()
  const statusColor = (status: string) => {
    if (status === 'available') return 'green'
    if (status === 'needs_config') return 'gold'
    if (status === 'adapter_only') return 'blue'
    return 'red'
  }
  const columns: ColumnsType<ParserStrategy> = [
    { title: '唯一名称', dataIndex: 'parser_name', render: (value) => <Typography.Text code>{value}</Typography.Text> },
    { title: '显示名称', dataIndex: 'display_name' },
    { title: '描述', dataIndex: 'description' },
    {
      title: '状态',
      dataIndex: 'availability_status',
      render: (value, record) => (
        <Tooltip title={record.availability_reason}>
          <Tag color={statusColor(value)}>{value}</Tag>
        </Tooltip>
      ),
    },
    { title: '支持后缀', dataIndex: 'supported_file_exts', render: (value: string[]) => <Space wrap>{value.map((item) => <Tag key={item}>{item}</Tag>)}</Space> },
    { title: '能力', dataIndex: 'capabilities', render: (value: string[]) => <Space wrap>{value.map((item) => <Tag key={item}>{item}</Tag>)}</Space> },
    { title: 'AutoRAG模块', dataIndex: 'autorag_module_type', render: (value) => value && <Tag>{value}</Tag> },
  ]

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>解析工具</Typography.Title>
        <Typography.Text type="secondary">从 ParserRegistry 暴露的解析策略列表，后续可接入自定义 parser。</Typography.Text>
      </div>
      <Card>
        <Table rowKey="parser_name" columns={columns} loading={parsers.isLoading} dataSource={parsers.data ?? []} />
      </Card>
    </Space>
  )
}
