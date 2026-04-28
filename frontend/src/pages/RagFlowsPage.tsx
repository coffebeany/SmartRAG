import { Button, Card, Popconfirm, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'
import { useDeleteRagFlow, useRagFlows } from '../api/hooks'
import type { RagFlow } from '../api/types'
import { TableActionButton } from '../components/TableActionButton'

export default function RagFlowsPage() {
  const flows = useRagFlows()
  const deleteFlow = useDeleteRagFlow()
  const retrievalNode = (flow: RagFlow) => flow.nodes.find((node) => node.node_type === 'retrieval')

  const columns: ColumnsType<RagFlow> = [
    { title: '流程名称', dataIndex: 'flow_name' },
    { title: '批次', dataIndex: 'batch_name', render: (value, record) => value ?? record.vector_run_id },
    { title: 'VectorDB', dataIndex: 'vectordb_name' },
    { title: 'Vector 状态', dataIndex: 'vector_run_status', render: (value) => <Tag>{value}</Tag> },
    {
      title: 'Retrieval',
      render: (_, record) => {
        const node = retrievalNode(record)
        return <Typography.Text code>{node?.module_type ?? 'vectordb'} top_k={String(node?.config?.top_k ?? record.retrieval_config?.top_k ?? 5)}</Typography.Text>
      },
    },
    {
      title: '节点',
      dataIndex: 'nodes',
      render: (nodes: RagFlow['nodes']) => (
        <Space wrap>{nodes.map((node, index) => <Tag key={`${index}-${node.module_type}`}>{node.node_type}:{node.module_type}</Tag>)}</Space>
      ),
    },
    { title: '创建时间', dataIndex: 'created_at', render: (value) => new Date(value).toLocaleString() },
    {
      title: '操作',
      render: (_, record) => (
        <Space>
          <Link className="tableActionLink" to={`/build/rag-flow-builder/${record.flow_id}`}>编辑</Link>
          <Link className="tableActionLink" to="/build/rag-experience">体验</Link>
          <Popconfirm title="删除该流程？" onConfirm={() => deleteFlow.mutate(record.flow_id)}>
            <TableActionButton danger loading={deleteFlow.isPending}>删除</TableActionButton>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div className="pageHeader">
        <div>
          <Typography.Title level={3}>流程列表</Typography.Title>
          <Typography.Text type="secondary">已保存的检索前后处理流程，可在流程体验中真实发问。</Typography.Text>
        </div>
        <Link to="/build/rag-flow-builder"><Button type="primary">新建流程</Button></Link>
      </div>
      <Card>
        <Table rowKey="flow_id" loading={flows.isLoading} columns={columns} dataSource={flows.data ?? []} />
      </Card>
    </Space>
  )
}
