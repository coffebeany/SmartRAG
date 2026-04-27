import { ReloadOutlined } from '@ant-design/icons'
import { App, Button, Card, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useParserStrategies, useRefreshParserStrategies } from '../api/hooks'
import type { ParserStrategy } from '../api/types'

export default function ParserStrategiesPage() {
  const { message } = App.useApp()
  const parsers = useParserStrategies()
  const refreshParsers = useRefreshParserStrategies()

  const statusColor = (status: string) => {
    if (status === 'available') return 'green'
    if (status === 'needs_config') return 'gold'
    if (status === 'adapter_only') return 'blue'
    return 'red'
  }

  const handleRefresh = () => {
    refreshParsers.mutate(undefined, {
      onSuccess: () => message.success('解析工具状态已刷新'),
      onError: (error) => message.error(error instanceof Error ? error.message : '刷新失败'),
    })
  }

  const columns: ColumnsType<ParserStrategy> = [
    {
      title: '唯一名称',
      dataIndex: 'parser_name',
      render: (value) => <Typography.Text code>{value}</Typography.Text>,
    },
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
    {
      title: '依赖',
      dataIndex: 'required_dependencies',
      render: (value: string[]) =>
        value.length ? <Space wrap>{value.map((item) => <Tag key={item}>{item}</Tag>)}</Space> : <Typography.Text type="secondary">无</Typography.Text>,
    },
    {
      title: '环境变量',
      dataIndex: 'required_env_vars',
      render: (value: string[]) =>
        value.length ? <Space wrap>{value.map((item) => <Tag key={item}>{item}</Tag>)}</Space> : <Typography.Text type="secondary">无</Typography.Text>,
    },
    {
      title: '支持后缀',
      dataIndex: 'supported_file_exts',
      render: (value: string[]) => <Space wrap>{value.map((item) => <Tag key={item}>{item}</Tag>)}</Space>,
    },
    {
      title: 'AutoRAG 模块',
      dataIndex: 'autorag_module_type',
      render: (value) => value && <Tag>{value}</Tag>,
    },
  ]

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div className="pageHeader">
        <div>
          <Typography.Title level={3}>解析工具</Typography.Title>
          <Typography.Text type="secondary">
            解析器状态会按当前后端运行环境实时计算；安装依赖后可手动刷新。
          </Typography.Text>
        </div>
        <Button
          icon={<ReloadOutlined />}
          loading={refreshParsers.isPending || parsers.isFetching}
          onClick={handleRefresh}
        >
          刷新状态
        </Button>
      </div>
      <Card>
        <Table rowKey="parser_name" columns={columns} loading={parsers.isLoading} dataSource={parsers.data ?? []} />
      </Card>
    </Space>
  )
}
