import { Card, Descriptions, Drawer, Progress, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  useParseFileRunDetail,
  useParseFileRunElements,
  useParseFileRuns,
  useParseRun,
} from '../api/hooks'
import type { ParseFileRun } from '../api/types'

type ElementRow = Record<string, unknown> & { __rowIndex: number }

const ELEMENT_PAGE_SIZE = 50

function elementLocator(element: Record<string, unknown>) {
  const keys = ['page', 'line', 'row_index', 'index']
  return keys
    .filter((key) => element[key] !== undefined && element[key] !== null)
    .map((key) => `${key}: ${String(element[key])}`)
    .join(' / ') || '-'
}

function elementPreview(element: Record<string, unknown>) {
  const text = element.text
  if (typeof text === 'string' && text.trim()) return text.slice(0, 240)
  const cells = element.cells
  if (Array.isArray(cells)) return cells.map(String).join(' | ').slice(0, 240)
  return JSON.stringify(element).slice(0, 240)
}

export default function ParseRunDetailPage() {
  const { runId } = useParams()
  const [selectedFileRunId, setSelectedFileRunId] = useState<string>()
  const [elementsPage, setElementsPage] = useState(1)
  const [elementsPageSize, setElementsPageSize] = useState(ELEMENT_PAGE_SIZE)
  const run = useParseRun(runId)
  const files = useParseFileRuns(runId)
  const detail = useParseFileRunDetail(runId, selectedFileRunId)
  const elements = useParseFileRunElements(
    runId,
    selectedFileRunId,
    (elementsPage - 1) * elementsPageSize,
    elementsPageSize,
  )
  const progressDone = (run.data?.completed_files ?? 0) + (run.data?.failed_files ?? 0)
  const progressPercent = run.data?.total_files
    ? Math.round((progressDone / run.data.total_files) * 100)
    : 0

  useEffect(() => {
    setElementsPage(1)
  }, [selectedFileRunId])

  const fileColumns: ColumnsType<ParseFileRun> = [
    {
      title: '文件',
      dataIndex: 'original_filename',
      render: (value, record) => (
        <Tooltip title="点击查看解析详情">
          <Typography.Link onClick={() => setSelectedFileRunId(record.file_run_id)}>
            {value}
          </Typography.Link>
        </Tooltip>
      ),
    },
    { title: '格式', dataIndex: 'file_ext', render: (value) => <Tag>{value}</Tag> },
    { title: '解析器', dataIndex: 'parser_name' },
    { title: '状态', dataIndex: 'status', render: (value) => <Tag>{value}</Tag> },
    { title: '质量分', dataIndex: 'quality_score', render: (value) => value ?? '-' },
    { title: '耗时', dataIndex: 'latency_ms', render: (value) => (value ? `${value} ms` : '-') },
    { title: '错误', dataIndex: 'error', ellipsis: true },
  ]

  const elementRows = useMemo<ElementRow[]>(
    () =>
      (elements.data?.items ?? []).map((item, index) => ({
        ...item,
        __rowIndex: (elementsPage - 1) * elementsPageSize + index + 1,
      })),
    [elements.data?.items, elementsPage, elementsPageSize],
  )

  const elementColumns: ColumnsType<ElementRow> = [
    { title: '#', dataIndex: '__rowIndex', width: 72 },
    { title: '类型', dataIndex: 'type', width: 130, render: (value) => <Tag>{String(value ?? '-')}</Tag> },
    { title: '位置', width: 180, render: (_, record) => elementLocator(record) },
    {
      title: '文本预览',
      render: (_, record) => <Typography.Text>{elementPreview(record)}</Typography.Text>,
    },
  ]

  const handleElementPageChange = (pagination: TablePaginationConfig) => {
    setElementsPage(pagination.current ?? 1)
    setElementsPageSize(pagination.pageSize ?? ELEMENT_PAGE_SIZE)
  }

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>解析任务详情</Typography.Title>
        <Typography.Text type="secondary">
          <Link to="/build/parse-runs">返回解析任务</Link>
        </Typography.Text>
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
          columns={fileColumns}
          dataSource={files.data ?? []}
          onRow={(record) => ({ onClick: () => setSelectedFileRunId(record.file_run_id) })}
        />
      </Card>
      <Drawer
        title="文件解析详情"
        width={920}
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
                  <Descriptions.Item label="Elements">
                    {elements.data
                      ? `${Math.min(elements.data.offset + 1, elements.data.total)}-${Math.min(
                          elements.data.offset + elements.data.items.length,
                          elements.data.total,
                        )} / ${elements.data.total}`
                      : '-'}
                  </Descriptions.Item>
                </Descriptions>
                <Card title="文本预览">
                  <Typography.Text type="secondary">仅展示前 5000 字符。</Typography.Text>
                  <pre className="preWrap">{detail.data.parsed_document.text_content.slice(0, 5000)}</pre>
                </Card>
                <Card title="Metadata">
                  <pre className="preWrap">{JSON.stringify(detail.data.parsed_document.document_metadata, null, 2)}</pre>
                </Card>
                <Card title="Elements">
                  <Table
                    rowKey="__rowIndex"
                    loading={elements.isLoading || elements.isFetching}
                    columns={elementColumns}
                    dataSource={elementRows}
                    expandable={{
                      expandedRowRender: (record) => (
                        <pre className="jsonViewer">{JSON.stringify(record, null, 2)}</pre>
                      ),
                    }}
                    locale={{ emptyText: '暂无 Elements' }}
                    pagination={{
                      current: elementsPage,
                      pageSize: elementsPageSize,
                      total: elements.data?.total ?? 0,
                      showSizeChanger: true,
                      pageSizeOptions: [20, 50, 100, 200, 500],
                      showTotal: (total, range) => `Elements: ${range[0]}-${range[1]} / ${total}`,
                    }}
                    onChange={handleElementPageChange}
                  />
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
