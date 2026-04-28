import { SendOutlined, ToolOutlined } from '@ant-design/icons'
import { Alert, Button, Collapse, Empty, Input, Select, Space, Spin, Tag, Typography, message } from 'antd'
import { useMemo, useRef, useState } from 'react'
import { API_BASE_URL } from '../api/client'
import { useAgentActions, useCreateSmartRagAgentRun, useModels } from '../api/hooks'
import type { AgentRunEvent, AgentRunEventType, AgentToolLog } from '../api/types'

const { Text, Title, Paragraph } = Typography

type ChatEntry = {
  role: 'user' | 'assistant' | 'system'
  content: string
}

const eventTypes: AgentRunEventType[] = [
  'message_delta',
  'reasoning_delta',
  'tool_call_started',
  'tool_call_result',
  'tool_call_error',
  'final_answer',
  'run_error',
]

function stringify(value: unknown) {
  if (typeof value === 'string') return value
  return JSON.stringify(value ?? {}, null, 2)
}

export default function SmartRAGAgentPage() {
  const [modelId, setModelId] = useState<string>()
  const [input, setInput] = useState('')
  const [running, setRunning] = useState(false)
  const [chat, setChat] = useState<ChatEntry[]>([])
  const [reasoning, setReasoning] = useState<string[]>([])
  const [toolLogs, setToolLogs] = useState<Record<string, AgentToolLog>>({})
  const eventSourceRef = useRef<EventSource | null>(null)
  const modelsQuery = useModels()
  const actionsQuery = useAgentActions()
  const createRun = useCreateSmartRagAgentRun()

  const llmOptions = useMemo(
    () =>
      (modelsQuery.data ?? [])
        .filter((model) => model.provider === 'openai_compatible' && model.model_category !== 'embedding' && model.enabled)
        .map((model) => ({
          label: `${model.display_name} · ${model.model_name}`,
          value: model.model_id,
        })),
    [modelsQuery.data],
  )

  const sortedLogs = Object.values(toolLogs).sort((left, right) => left.created_at.localeCompare(right.created_at))

  const applyEvent = (event: AgentRunEvent) => {
    const payload = event.payload
    if (event.event_type === 'message_delta') {
      const role = payload.role === 'system' ? 'system' : 'assistant'
      const content = String(payload.content ?? '')
      if (content && role !== 'system') {
        setChat((items) => [...items, { role, content }])
      }
    }
    if (event.event_type === 'reasoning_delta') {
      const content = String(payload.content ?? '')
      if (content) setReasoning((items) => [...items, content])
    }
    if (event.event_type === 'tool_call_started') {
      const id = String(payload.tool_log_id)
      setToolLogs((items) => ({
        ...items,
        [id]: {
          tool_log_id: id,
          run_id: event.run_id,
          tool_name: String(payload.tool_name ?? ''),
          tool_args: (payload.args as Record<string, unknown>) ?? {},
          status: String(payload.status ?? 'running'),
          created_at: event.created_at,
        },
      }))
    }
    if (event.event_type === 'tool_call_result' || event.event_type === 'tool_call_error') {
      const id = String(payload.tool_log_id)
      setToolLogs((items) => ({
        ...items,
        [id]: {
          ...(items[id] ?? {
            tool_log_id: id,
            run_id: event.run_id,
            tool_name: String(payload.tool_name ?? ''),
            tool_args: {},
            created_at: event.created_at,
          }),
          status: String(payload.status ?? (event.event_type === 'tool_call_error' ? 'error' : 'success')),
          output: payload.output,
          error: typeof payload.error === 'string' ? payload.error : null,
          latency_ms: typeof payload.latency_ms === 'number' ? payload.latency_ms : null,
        },
      }))
    }
    if (event.event_type === 'final_answer') {
      setRunning(false)
    }
    if (event.event_type === 'run_error') {
      setRunning(false)
      message.error(String(payload.error ?? 'Agent run failed'))
    }
  }

  const startRun = async () => {
    const content = input.trim()
    if (!modelId || !content) return
    eventSourceRef.current?.close()
    setInput('')
    setRunning(true)
    setReasoning([])
    setToolLogs({})
    setChat((items) => [...items, { role: 'user', content }])
    try {
      const run = await createRun.mutateAsync({ model_id: modelId, message: content })
      const source = new EventSource(`${API_BASE_URL}/smartrag-agent/runs/${run.run_id}/events`)
      eventSourceRef.current = source
      eventTypes.forEach((eventType) => {
        source.addEventListener(eventType, (rawEvent) => {
          const parsed = JSON.parse((rawEvent as MessageEvent).data) as AgentRunEvent
          applyEvent(parsed)
          if (eventType === 'final_answer' || eventType === 'run_error') {
            source.close()
          }
        })
      })
      source.onerror = () => {
        setRunning(false)
        source.close()
      }
    } catch (error) {
      setRunning(false)
      message.error(error instanceof Error ? error.message : 'Failed to start SmartRAG Agent')
    }
  }

  return (
    <div className="pageStack agentConsolePage">
      <div className="pageHeader">
        <div>
          <Title level={3}>SmartRAG Agent</Title>
          <Text type="secondary">通过 Registry tools 观察和执行材料、解析、分块、向量化、RAG 与测评操作。</Text>
        </div>
        <Space>
          <Tag color="blue">{actionsQuery.data?.length ?? 0} actions</Tag>
          {running ? <Tag color="processing">running</Tag> : <Tag>idle</Tag>}
        </Space>
      </div>

      <div className="agentConsoleGrid">
        <section className="agentChatPanel">
          <div className="agentChatStream">
            {chat.length === 0 ? (
              <Empty description="选择 LLM 后发送消息" />
            ) : (
              chat.map((item, index) => (
                <div key={`${item.role}-${index}`} className={`agentBubble ${item.role}`}>
                  <Text strong>{item.role === 'user' ? 'You' : 'SmartRAG Agent'}</Text>
                  <Paragraph>{item.content}</Paragraph>
                </div>
              ))
            )}
            {running && (
              <div className="agentBubble assistant">
                <Spin size="small" /> <Text type="secondary">Agent is working...</Text>
              </div>
            )}
          </div>
          <div className="agentComposer">
            <Select
              className="agentModelSelect"
              placeholder="选择 OpenAI-compatible LLM"
              options={llmOptions}
              value={modelId}
              onChange={setModelId}
              loading={modelsQuery.isLoading}
            />
            <Input.TextArea
              autoSize={{ minRows: 2, maxRows: 6 }}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onPressEnter={(event) => {
                if (!event.shiftKey) {
                  event.preventDefault()
                  void startRun()
                }
              }}
              placeholder="询问项目状态，或要求 Agent 创建、运行、观测 SmartRAG 操作"
            />
            <Button type="primary" icon={<SendOutlined />} loading={running || createRun.isPending} disabled={!modelId || !input.trim()} onClick={startRun}>
              Send
            </Button>
          </div>
        </section>

        <aside className="agentToolPanel">
          <Title level={5}>Tool Logs</Title>
          {reasoning.length > 0 && (
            <Alert
              className="agentReasoning"
              type="info"
              showIcon
              message="Reasoning Summary"
              description={reasoning.join('\n')}
            />
          )}
          {sortedLogs.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No tool calls" />
          ) : (
            <Collapse
              size="small"
              items={sortedLogs.map((log) => ({
                key: log.tool_log_id,
                label: (
                  <Space>
                    <ToolOutlined />
                    <Text>{log.tool_name}</Text>
                    <Tag color={log.status === 'success' ? 'green' : log.status === 'error' ? 'red' : 'blue'}>{log.status}</Tag>
                    {log.latency_ms != null && <Text type="secondary">{log.latency_ms}ms</Text>}
                  </Space>
                ),
                children: (
                  <div className="agentToolBody">
                    <Text type="secondary">Args</Text>
                    <pre>{stringify(log.tool_args)}</pre>
                    <Text type="secondary">Output</Text>
                    <pre>{stringify(log.error ?? log.output)}</pre>
                  </div>
                ),
              }))}
            />
          )}
        </aside>
      </div>
    </div>
  )
}
