import { Card, Descriptions, Drawer, Progress, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useChunkFileRunChunks, useChunkFileRuns, useChunkRun } from '../api/hooks'
import type { Chunk, ChunkFileRun } from '../api/types'

const CHUNK_PAGE_SIZE = 50

export default function ChunkRunDetailPage() {
  const { runId } = useParams()
  const [selectedFileRunId, setSelectedFileRunId] = useState<string>()
  const [chunkPage, setChunkPage] = useState(1)
  const [chunkPageSize, setChunkPageSize] = useState(CHUNK_PAGE_SIZE)
  const run = useChunkRun(runId)
  const files = useChunkFileRuns(runId)
  const chunks = useChunkFileRunChunks(
    runId,
    selectedFileRunId,
    (chunkPage - 1) * chunkPageSize,
    chunkPageSize,
  )
  const progressDone = (run.data?.completed_files ?? 0) + (run.data?.failed_files ?? 0)
  const progressPercent = run.data?.total_files ? Math.round((progressDone / run.data.total_files) * 100) : 0

  useEffect(() => {
    setChunkPage(1)
  }, [selectedFileRunId])

  const fileColumns: ColumnsType<ChunkFileRun> = [
    {
      title: '文件',
      dataIndex: 'original_filename',
      render: (value, record) => (
        <Typography.Link onClick={() => setSelectedFileRunId(record.file_run_id)}>{value}</Typography.Link>
      ),
    },
    { title: 'Parser', dataIndex: 'parser_name' },
    { title: '状态', dataIndex: 'status', render: (value) => <Tag>{value}</Tag> },
    { title: 'Chunks', dataIndex: 'chunk_count' },
    { title: '耗时', dataIndex: 'latency_ms', render: (value) => (value ? `${value} ms` : '-') },
    { title: '错误', dataIndex: 'error', ellipsis: true },
  ]

  const chunkRows = useMemo(() => chunks.data?.items ?? [], [chunks.data?.items])
  const chunkColumns: ColumnsType<Chunk> = [
    { title: '#', dataIndex: 'chunk_index', width: 72 },
    { title: '字符', dataIndex: 'char_count', width: 90 },
    { title: 'Token', dataIndex: 'token_count', width: 90 },
    { title: '范围', width: 140, render: (_, record) => `${record.start_char}-${record.end_char}` },
    {
      title: '内容预览',
      render: (_, record) => <Typography.Text>{record.contents.slice(0, 260)}</Typography.Text>,
    },
  ]

  const handleChunkPageChange = (pagination: TablePaginationConfig) => {
    setChunkPage(pagination.current ?? 1)
    setChunkPageSize(pagination.pageSize ?? CHUNK_PAGE_SIZE)
  }

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>分块任务详情</Typography.Title>
        <Typography.Text type="secondary">
          <Link to="/build/chunk-runs">返回分块任务</Link>
        </Typography.Text>
      </div>
      <Card loading={run.isLoading}>
        {run.data && (
          <Space direction="vertical" className="pageStack">
            <Descriptions column={4}>
              <Descriptions.Item label="批次">{run.data.batch_name ?? run.data.batch_id}</Descriptions.Item>
              <Descriptions.Item label="分块工具">{run.data.chunker_name}</Descriptions.Item>
              <Descriptions.Item label="状态">{run.data.status}</Descriptions.Item>
              <Descriptions.Item label="Chunks">{run.data.total_chunks}</Descriptions.Item>
            </Descriptions>
            <Progress percent={progressPercent} format={() => `${progressDone}/${run.data?.total_files ?? 0}`} />
            <Descriptions column={4}>
              <Descriptions.Item label="平均长度">{String(run.data.stats.avg_char_count ?? '-')}</Descriptions.Item>
              <Descriptions.Item label="最小长度">{String(run.data.stats.min_char_count ?? '-')}</Descriptions.Item>
              <Descriptions.Item label="最大长度">{String(run.data.stats.max_char_count ?? '-')}</Descriptions.Item>
              <Descriptions.Item label="Artifact">{run.data.artifact_uri ?? '-'}</Descriptions.Item>
            </Descriptions>
            <Card title="配置">
              <pre className="jsonViewer">{JSON.stringify(run.data.chunker_config, null, 2)}</pre>
            </Card>
          </Space>
        )}
      </Card>
      <Card>
        <Table
          rowKey="file_run_id"
          loading={files.isLoading}
          columns={fileColumns}
          dataSource={files.data ?? []}
          onRow={(record) => ({ onClick: () => setSelectedFileRunId(record.file_run_id) })}
        />
      </Card>
      <Drawer
        title="文件 Chunk 结果"
        width={980}
        open={Boolean(selectedFileRunId)}
        onClose={() => setSelectedFileRunId(undefined)}
      >
        <Table
          rowKey="chunk_id"
          loading={chunks.isLoading || chunks.isFetching}
          columns={chunkColumns}
          dataSource={chunkRows}
          expandable={{
            expandedRowRender: (record) => <pre className="jsonViewer">{JSON.stringify(record, null, 2)}</pre>,
          }}
          pagination={{
            current: chunkPage,
            pageSize: chunkPageSize,
            total: chunks.data?.total ?? 0,
            showSizeChanger: true,
            pageSizeOptions: [20, 50, 100, 200, 500],
            showTotal: (total, range) => `Chunks: ${range[0]}-${range[1]} / ${total}`,
          }}
          onChange={handleChunkPageChange}
        />
      </Drawer>
    </Space>
  )
}
