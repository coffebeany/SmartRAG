import { Alert, Card, Descriptions, Progress, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link, useParams } from 'react-router-dom'
import { useVectorFileRuns, useVectorRun } from '../api/hooks'
import type { VectorFileRun } from '../api/types'

export default function VectorRunDetailPage() {
  const { runId } = useParams()
  const run = useVectorRun(runId)
  const files = useVectorFileRuns(runId)
  const data = run.data

  const columns: ColumnsType<VectorFileRun> = [
    { title: '文件', dataIndex: 'original_filename', render: (value, record) => value ?? record.source_file_id },
    { title: '状态', dataIndex: 'status', render: (value) => <Tag>{value}</Tag> },
    { title: 'Chunks', dataIndex: 'chunk_count' },
    { title: 'Vectors', dataIndex: 'vector_count' },
    { title: '失败向量', dataIndex: 'failed_vectors' },
    { title: '耗时(ms)', dataIndex: 'latency_ms', render: (value) => value ?? 'NA' },
    { title: '错误', dataIndex: 'error', render: (value) => value || 'NA' },
  ]

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Link to="/build/vector-runs">返回向量化任务</Link>
        <Typography.Title level={3}>向量化详情</Typography.Title>
      </div>
      {data && (
        <>
          {data.error_summary && <Alert type="error" showIcon message={data.error_summary} />}
          <Card>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="状态">
                <Tag>{data.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="进度">
                <Progress
                  percent={data.total_files ? Math.round((data.completed_files / data.total_files) * 100) : 0}
                  size="small"
                />
              </Descriptions.Item>
              <Descriptions.Item label="批次">{data.batch_name ?? data.batch_id}</Descriptions.Item>
              <Descriptions.Item label="Chunk Run">{data.chunk_run_id}</Descriptions.Item>
              <Descriptions.Item label="VectorDB">{data.vectordb_name}</Descriptions.Item>
              <Descriptions.Item label="Collection">{data.collection_name}</Descriptions.Item>
              <Descriptions.Item label="存储位置">{data.storage_uri}</Descriptions.Item>
              <Descriptions.Item label="相似度">{data.similarity_metric}</Descriptions.Item>
              <Descriptions.Item label="维度">{data.embedding_dimension ?? 'NA'}</Descriptions.Item>
              <Descriptions.Item label="Vectors">{data.total_vectors}</Descriptions.Item>
              <Descriptions.Item label="开始时间">
                {data.started_at ? new Date(data.started_at).toLocaleString() : 'NA'}
              </Descriptions.Item>
              <Descriptions.Item label="结束时间">
                {data.ended_at ? new Date(data.ended_at).toLocaleString() : 'NA'}
              </Descriptions.Item>
            </Descriptions>
          </Card>
          <Card title="策略快照">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Embedding 模型">
                <pre>{JSON.stringify(data.embedding_model_snapshot, null, 2)}</pre>
              </Descriptions.Item>
              <Descriptions.Item label="VectorDB 配置">
                <pre>{JSON.stringify(data.vectordb_config, null, 2)}</pre>
              </Descriptions.Item>
              <Descriptions.Item label="Embedding 策略">
                <pre>{JSON.stringify(data.embedding_config, null, 2)}</pre>
              </Descriptions.Item>
              <Descriptions.Item label="索引策略">
                <pre>{JSON.stringify(data.index_config, null, 2)}</pre>
              </Descriptions.Item>
              <Descriptions.Item label="文件选择">
                <pre>{JSON.stringify(data.file_selection, null, 2)}</pre>
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </>
      )}
      <Card title="文件进度">
        <Table rowKey="file_run_id" loading={files.isLoading} columns={columns} dataSource={files.data ?? []} />
      </Card>
    </Space>
  )
}
