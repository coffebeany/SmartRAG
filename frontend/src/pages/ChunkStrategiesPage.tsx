import { ReloadOutlined } from '@ant-design/icons'
import { App, Button, Card, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useChunkStrategies, useRefreshChunkStrategies } from '../api/hooks'
import type { ChunkStrategy } from '../api/types'

function statusColor(status: string) {
  if (status === 'available') return 'green'
  if (status === 'needs_config') return 'gold'
  if (status === 'adapter_only') return 'blue'
  return 'red'
}

export default function ChunkStrategiesPage() {
  const { message } = App.useApp()
  const chunkers = useChunkStrategies()
  const refreshChunkers = useRefreshChunkStrategies()

  const handleRefresh = () => {
    refreshChunkers.mutate(undefined, {
      onSuccess: () => message.success('分块工具状态已刷新'),
      onError: (error) => message.error(error instanceof Error ? error.message : '刷新失败'),
    })
  }

  const columns: ColumnsType<ChunkStrategy> = [
    {
      title: '唯一名称',
      dataIndex: 'chunker_name',
      render: (value) => <Typography.Text code>{value}</Typography.Text>,
    },
    { title: '显示名称', dataIndex: 'display_name' },
    { title: '模块', dataIndex: 'module_type', render: (value) => <Tag>{value}</Tag> },
    { title: '方法', dataIndex: 'chunk_method' },
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
        value.length ? (
          <Space wrap>{value.map((item) => <Tag key={item}>{item}</Tag>)}</Space>
        ) : (
          <Typography.Text type="secondary">无</Typography.Text>
        ),
    },
    {
      title: '能力',
      dataIndex: 'capabilities',
      render: (value: string[]) => <Space wrap>{value.map((item) => <Tag key={item}>{item}</Tag>)}</Space>,
    },
  ]

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div className="pageHeader">
        <div>
          <Typography.Title level={3}>分块工具</Typography.Title>
          <Typography.Text type="secondary">
            分块工具状态会按当前后端运行环境实时计算；安装可选依赖后可手动刷新。
          </Typography.Text>
        </div>
        <Button
          icon={<ReloadOutlined />}
          loading={refreshChunkers.isPending || chunkers.isFetching}
          onClick={handleRefresh}
        >
          刷新状态
        </Button>
      </div>
      <Card>
        <Table rowKey="chunker_name" columns={columns} loading={chunkers.isLoading} dataSource={chunkers.data ?? []} />
      </Card>
    </Space>
  )
}
