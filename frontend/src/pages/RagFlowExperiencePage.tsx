import { Alert, App, Button, Card, Descriptions, Input, Select, Space, Tag, Timeline, Typography } from 'antd'
import { useState } from 'react'
import { useRagFlows, useRunRagFlow } from '../api/hooks'
import type { RagFlowRun } from '../api/types'
import LangfuseTraceLink from '../components/LangfuseTraceLink'

function statusColor(status?: string) {
  if (status === 'success' || status === 'completed') return 'green'
  if (status === 'failed') return 'red'
  return 'blue'
}

function titleCase(value: unknown) {
  return String(value ?? '').replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

export default function RagFlowExperiencePage() {
  const { message } = App.useApp()
  const flows = useRagFlows()
  const runFlow = useRunRagFlow()
  const [flowId, setFlowId] = useState<string>()
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<RagFlowRun | null>(null)

  const selectedFlow = (flows.data ?? []).find((flow) => flow.flow_id === flowId)
  const selectedRetrieval = selectedFlow?.nodes.find((node) => node.node_type === 'retrieval')
  const flowOptions = (flows.data ?? []).map((flow) => ({
    value: flow.flow_id,
    label: flow.flow_name,
    meta: `${flow.batch_name ?? flow.vector_run_id} / ${flow.vectordb_name ?? 'VectorDB'}`,
  }))

  const submit = () => {
    if (!flowId || !query.trim()) {
      message.error('请选择流程并输入问题')
      return
    }
    runFlow.mutate(
      { flowId, query },
      {
        onSuccess: (data) => setResult(data),
        onError: (error) => message.error(error instanceof Error ? error.message : '执行失败'),
      },
    )
  }

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <div>
        <Typography.Title level={3}>流程体验</Typography.Title>
        <Typography.Text type="secondary">选择流程真实发问，查看每个节点的 activate 状态和中间输出。</Typography.Text>
      </div>
      <Card>
        <Space direction="vertical" size={12} className="fullWidth">
          <Select
            className="wideFlowSelect"
            popupClassName="wideFlowSelectPopup"
            placeholder="选择流程"
            value={flowId}
            onChange={setFlowId}
            options={flowOptions}
            optionRender={(option) => {
              const data = option.data as { label: string; meta: string }
              return (
                <div className="flowSelectOption">
                  <strong title={data.label}>{data.label}</strong>
                  <span className="flowSelectMeta" title={data.meta}>{data.meta}</span>
                </div>
              )
            }}
          />
          {selectedFlow && (
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="VectorDB">{selectedFlow.vectordb_name}</Descriptions.Item>
              <Descriptions.Item label="Retrieval">{selectedRetrieval?.module_type ?? 'vectordb'} top_k={String(selectedRetrieval?.config?.top_k ?? selectedFlow.retrieval_config?.top_k ?? 5)}</Descriptions.Item>
              <Descriptions.Item label="节点数">{selectedFlow.nodes.length}</Descriptions.Item>
              <Descriptions.Item label="状态">{selectedFlow.enabled ? 'enabled' : 'disabled'}</Descriptions.Item>
            </Descriptions>
          )}
          <Input.TextArea rows={4} placeholder="输入问题" value={query} onChange={(event) => setQuery(event.target.value)} />
          <Button type="primary" loading={runFlow.isPending} onClick={submit}>运行流程</Button>
        </Space>
      </Card>
      {result?.status === 'failed' && <Alert type="error" showIcon message={result.error || '执行失败'} />}
      {result && (
        <Card title="中间输出" extra={<LangfuseTraceLink traceId={result.langfuse_trace_id} />}>
          <Timeline
            items={(result.trace_events ?? []).map((event, index) => ({
              color: statusColor(event.status as string),
              children: (
                <Space direction="vertical" className="fullWidth" size={6}>
                  <Space wrap>
                    <Typography.Text strong>
                      {titleCase(event.node_type)} {event.activated ? 'activated' : 'not activated'}
                    </Typography.Text>
                    <Tag>{String(event.module_type)}</Tag>
                    <Tag color={statusColor(event.status as string)}>{String(event.status)}</Tag>
                    <Typography.Text type="secondary">{String(event.latency_ms ?? 0)} ms</Typography.Text>
                  </Space>
                  <pre className="jsonViewer">{JSON.stringify(event.output_summary ?? {}, null, 2)}</pre>
                  {event.error ? <Typography.Text type="danger">{String(event.error)}</Typography.Text> : null}
                </Space>
              ),
              key: `${index}-${event.node_type}`,
            }))}
          />
        </Card>
      )}
      {result && (
        <Card title="最终回答">
          {result.answer ? (
            <Typography.Paragraph className="passageText">{result.answer}</Typography.Paragraph>
          ) : (
            <Typography.Text type="secondary">该流程未配置 Answer Generator。</Typography.Text>
          )}
        </Card>
      )}
      {result && (
        <Card title="最终 Passages">
          <Space direction="vertical" size={12} className="fullWidth">
            {(result.final_passages ?? []).map((passage, index) => (
              <Card size="small" key={String(passage.chunk_id ?? index)}>
                <Space direction="vertical" className="fullWidth">
                  <Space wrap>
                    <Tag>#{index + 1}</Tag>
                    <Typography.Text code>{String(passage.chunk_id ?? '')}</Typography.Text>
                    <Typography.Text type="secondary">score={Number(passage.score ?? 0).toFixed(4)}</Typography.Text>
                    {passage.original_filename ? <Tag>{String(passage.original_filename)}</Tag> : null}
                  </Space>
                  <Typography.Paragraph className="passageText">{String(passage.contents ?? '')}</Typography.Paragraph>
                </Space>
              </Card>
            ))}
          </Space>
        </Card>
      )}
    </Space>
  )
}
