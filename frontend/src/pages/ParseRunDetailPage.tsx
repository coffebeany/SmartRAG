import { Card, Descriptions, Drawer, Progress, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useParseFileRunDetail, useParseFileRuns, useParseRun } from '../api/hooks'
import type { ParseFileRun } from '../api/types'

export default function ParseRunDetailPage() {
  const { runId } = useParams()
  const [selectedFileRunId, setSelectedFileRunId] = useState<string>()
  const run = useParseRun(runId)
  const files = useParseFileRuns(runId)
  const detail = useParseFileRunDetail(runId, selectedFileRunId)
  const progressDone = (run.data?.completed_files ?? 0) + (run.data?.failed_files ?? 0)
  const progressPercent = run.data?.total_files ? Math.round((progressDone / run.data.total_files) * 100) : 0

  const columns: ColumnsType<ParseFileRun> = [
    { title: '文件', dataIndex: 'original_filename' },
    { title: '格式', dataIndex: 'file_ext', render: (value) => <Tag>{value}</Tag> },
    { title: '解析器', dataIndex: 'parser_name' },
    { title: '状态', dataIndex: 'status', render: (value) => <Tag>{value}</Tag> },
    { title: '质量分', dataIndex: 'quality_score', render: (value) => value ?? '-' },
    { title: '耗时', dataIndex: 'latency_ms', render: (value) => value ? `${value} ms` : '-' },
    { title: '错误', dataIndex: 'error', ellipsis: true },
  ]

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>解析任务详情</Typography.Title>
        <Typography.Text type="secondary"><Link to="/build/parse-runs">返回解析情况</Link></Typography.Text>
      </div>
      <Card loading={run.isLoading}>
        {run.data && (
          <Space direction="vertical" className="pageStack">
            <Descriptions column={4}>
              <Descriptions.Item label="批次">{run.data.batch_name ?? run.data.batch_id}</Descriptions.Item>
              <Descriptions.Item label="状态">{run.data.status}</Descriptions.Item>
              <Descriptions.Item label="成功">{run.data.completed_files}</Descriptions.Item>
              <Descriptions.Item label="失败">{run.data.failed_files}</Descriptions.Item>
            </Descriptions>
            <Progress percent={progressPercent} format={() => `${progressDone}/${run.data?.total_files ?? 0}`} />
          </Space>
        )}
      </Card>
      <Card>
        <Table
          rowKey="file_run_id"
          loading={files.isLoading}
          columns={columns}
          dataSource={files.data ?? []}
          onRow={(record) => ({ onClick: () => setSelectedFileRunId(record.file_run_id) })}
        />
      </Card>
      <Drawer
        title="文件解析详情"
        width={720}
        open={Boolean(selectedFileRunId)}
        onClose={() => setSelectedFileRunId(undefined)}
      >
        {detail.data && (
          <Space direction="vertical" size={16} className="pageStack">
            <Descriptions column={1} bordered>
              <Descriptions.Item label="文件">{detail.data.file_run.original_filename}</Descriptions.Item>
              <Descriptions.Item label="解析器">{detail.data.file_run.parser_name}</Descriptions.Item>
              <Descriptions.Item label="状态">{detail.data.file_run.status}</Descriptions.Item>
              <Descriptions.Item label="质量分">{detail.data.file_run.quality_score ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="错误">{detail.data.file_run.error ?? '-'}</Descriptions.Item>
            </Descriptions>
            {detail.data.parsed_document ? (
              <>
                <Descriptions column={2} bordered>
                  <Descriptions.Item label="字符数">{detail.data.parsed_document.char_count}</Descriptions.Item>
                  <Descriptions.Item label="页数">{detail.data.parsed_document.pages}</Descriptions.Item>
                  <Descriptions.Item label="Artifact">{detail.data.parsed_document.artifact_uri ?? '-'}</Descriptions.Item>
                </Descriptions>
                <Card title="文本预览">
                  <pre className="preWrap">{detail.data.parsed_document.text_content.slice(0, 5000)}</pre>
                </Card>
                <Card title="Metadata">
                  <pre className="preWrap">{JSON.stringify(detail.data.parsed_document.document_metadata, null, 2)}</pre>
                </Card>
                <Card title="Elements">
                  <pre className="preWrap">{JSON.stringify(detail.data.parsed_document.elements.slice(0, 20), null, 2)}</pre>
                </Card>
              </>
            ) : (
              <Typography.Text type="secondary">暂无解析产物。</Typography.Text>
            )}
          </Space>
        )}
      </Drawer>
    </Space>
  )
}
