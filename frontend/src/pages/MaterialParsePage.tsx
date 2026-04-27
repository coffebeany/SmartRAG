import { App, Button, Card, Form, Input, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCreateParseRun, useMaterialBatches, useParsePlan } from '../api/hooks'
import type { ParsePlanFile, ParserStrategy } from '../api/types'

const EXECUTABLE_STATUSES = new Set(['available', 'needs_config'])

function stringifyConfig(config: Record<string, unknown> | undefined) {
  return JSON.stringify(config ?? {}, null, 2)
}

function statusColor(status?: string) {
  if (status === 'available') return 'green'
  if (status === 'needs_config') return 'gold'
  if (status === 'adapter_only') return 'blue'
  return 'red'
}

export default function MaterialParsePage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [batchId, setBatchId] = useState<string>()
  const [parserByFile, setParserByFile] = useState<Record<string, string>>({})
  const [configByFile, setConfigByFile] = useState<Record<string, string>>({})
  const batches = useMaterialBatches()
  const parsePlan = useParsePlan(batchId)
  const createParseRun = useCreateParseRun()

  useEffect(() => {
    if (!parsePlan.data) return
    const parserMap: Record<string, string> = {}
    const configMap: Record<string, string> = {}
    parsePlan.data.files.forEach((item) => {
      if (item.default_parser_name) parserMap[item.file.file_id] = item.default_parser_name
      configMap[item.file.file_id] = stringifyConfig(item.default_parser_config)
    })
    setParserByFile(parserMap)
    setConfigByFile(configMap)
  }, [parsePlan.data])

  const selectedParser = (row: ParsePlanFile): ParserStrategy | undefined =>
    row.parser_options.find((parser) => parser.parser_name === parserByFile[row.file.file_id])

  const changeParser = (row: ParsePlanFile, parserName: string) => {
    const parser = row.parser_options.find((item) => item.parser_name === parserName)
    setParserByFile((prev) => ({ ...prev, [row.file.file_id]: parserName }))
    setConfigByFile((prev) => ({
      ...prev,
      [row.file.file_id]: stringifyConfig(parser?.default_config),
    }))
  }

  const parserLabel = (parser: ParserStrategy) => (
    <Space size={8}>
      <span>{parser.display_name}</span>
      <Tag color={statusColor(parser.availability_status)}>{parser.availability_status}</Tag>
    </Space>
  )

  const columns: ColumnsType<ParsePlanFile> = useMemo(
    () => [
      { title: '文件', render: (_, row) => row.file.original_filename },
      { title: '格式', width: 90, render: (_, row) => <Tag>{row.file.file_ext}</Tag> },
      {
        title: '解析器',
        width: 340,
        render: (_, row) => (
          <Select
            className="fullWidth"
            value={parserByFile[row.file.file_id]}
            onChange={(value) => changeParser(row, value)}
            options={row.parser_options.map((parser) => ({
              value: parser.parser_name,
              label: parserLabel(parser),
              disabled: !EXECUTABLE_STATUSES.has(parser.availability_status),
            }))}
          />
        ),
      },
      {
        title: '状态',
        width: 140,
        render: (_, row) => {
          const parser = selectedParser(row)
          if (!parser) return <Tag color="red">未选择</Tag>
          return (
            <Tooltip title={parser.availability_reason}>
              <Tag color={statusColor(parser.availability_status)}>{parser.availability_status}</Tag>
            </Tooltip>
          )
        },
      },
      {
        title: '配置 JSON',
        width: 360,
        render: (_, row) => {
          const parser = selectedParser(row)
          return (
            <Input.TextArea
              rows={parser?.requires_config ? 4 : 2}
              value={configByFile[row.file.file_id] ?? '{}'}
              placeholder={parser?.requires_config ? '{"jq_schema": ".content"}' : '{}'}
              onChange={(event) =>
                setConfigByFile((prev) => ({ ...prev, [row.file.file_id]: event.target.value }))
              }
            />
          )
        },
      },
    ],
    [configByFile, parserByFile],
  )

  const startParse = () => {
    if (!parsePlan.data || !batchId) return
    try {
      const files = parsePlan.data.files.map((item) => ({
        file_id: item.file.file_id,
        parser_name: parserByFile[item.file.file_id],
        parser_config: JSON.parse(configByFile[item.file.file_id] || '{}'),
      }))
      if (files.some((item) => !item.parser_name)) {
        message.error('请为所有文件选择解析器')
        return
      }
      createParseRun.mutate(
        { batch_id: batchId, files },
        {
          onSuccess: (run) => {
            message.success('解析任务已启动')
            navigate(`/build/parse-runs/${run.run_id}`)
          },
        },
      )
    } catch {
      message.error('配置 JSON 格式不正确')
    }
  }

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>材料解析</Typography.Title>
        <Typography.Text type="secondary">
          选择一个材料批次，系统会按默认处理规则自动填充解析器和配置，也可以逐文件调整。
        </Typography.Text>
      </div>
      <Card>
        <Form form={form} layout="vertical">
          <Form.Item label="材料批次">
            <Select
              placeholder="选择材料批次"
              value={batchId}
              onChange={setBatchId}
              options={(batches.data ?? []).map((batch) => ({
                value: batch.batch_id,
                label: `${batch.batch_name} (${batch.file_count} files)`,
              }))}
            />
          </Form.Item>
        </Form>
      </Card>
      <Card>
        <Table
          rowKey={(row) => row.file.file_id}
          loading={parsePlan.isLoading}
          columns={columns}
          dataSource={parsePlan.data?.files ?? []}
          pagination={false}
        />
        <Button
          type="primary"
          className="uploadAction"
          disabled={!parsePlan.data || parsePlan.data.files.length === 0}
          loading={createParseRun.isPending}
          onClick={startParse}
        >
          开始解析
        </Button>
      </Card>
    </Space>
  )
}
