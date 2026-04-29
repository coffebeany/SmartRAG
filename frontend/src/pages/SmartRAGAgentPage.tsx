import { SendOutlined, StopOutlined, ToolOutlined } from '@ant-design/icons'
import { Button, Collapse, Drawer, Empty, Input, Segmented, Select, Space, Spin, Tag, Typography, message } from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'
import { API_BASE_URL, apiClient } from '../api/client'
import { useAgentActions, useCancelSmartRagAgentRun, useCreateSmartRagAgentRun, useModels, useSmartRagAgentRun } from '../api/hooks'
import type { AgentActionSpec, AgentRunEvent, AgentRunEventType, AgentToolLog, SmartRagAgentRun } from '../api/types'

const { Text, Title, Paragraph } = Typography

type TimelineTextItem = {
  id: string
  type: 'user_message' | 'assistant_message' | 'reasoning' | 'system_notice'
  content: string
}

type TimelineToolItem = {
  id: string
  type: 'tool_call'
  log: AgentToolLog
}

type TimelineItem = TimelineTextItem | TimelineToolItem

const eventTypes: AgentRunEventType[] = [
  'message_delta',
  'reasoning_delta',
  'tool_call_started',
  'tool_call_result',
  'tool_call_error',
  'final_answer',
  'run_error',
  'run_cancelled',
]

const STORAGE_KEYS = {
  activeRunId: 'smartrag.agent.active_run_id',
  draftInput: 'smartrag.agent.draft_input',
  selectedModelId: 'smartrag.agent.selected_model_id',
}

function stringify(value: unknown) {
  if (typeof value === 'string') return value
  return JSON.stringify(value ?? {}, null, 2)
}

function readStorage(key: string) {
  try {
    return window.localStorage.getItem(key) ?? ''
  } catch {
    return ''
  }
}

function writeStorage(key: string, value: string) {
  try {
    if (value) {
      window.localStorage.setItem(key, value)
    } else {
      window.localStorage.removeItem(key)
    }
  } catch {
    // Ignore storage errors; the running page state remains authoritative.
  }
}

function isTerminalRun(status: SmartRagAgentRun['status']) {
  return status === 'completed' || status === 'failed' || status === 'cancelled'
}

function getStatusColor(status: string) {
  if (status === 'success') return 'green'
  if (status === 'error') return 'red'
  return 'blue'
}

function actionMatchesSearch(action: AgentActionSpec, keyword: string) {
  if (!keyword) return true
  const haystack = [action.name, action.title, action.description, action.permission_scope, action.tags.join(' ')]
    .join(' ')
    .toLowerCase()
  return haystack.includes(keyword.toLowerCase())
}

function buildTimelineFromRun(run: SmartRagAgentRun) {
  const items: TimelineItem[] = [{ id: `user-${run.run_id}`, type: 'user_message', content: run.message }]
  let lastSequence = 0
  let hasAssistantOutput = false
  const events = [...run.events].sort((left, right) => left.sequence - right.sequence)

  const appendAssistant = (content: string, id: string) => {
    hasAssistantOutput = true
    const last = items[items.length - 1]
    if (last?.type === 'assistant_message') {
      items[items.length - 1] = { ...last, content: `${last.content}${content}` }
      return
    }
    items.push({ id, type: 'assistant_message', content })
  }

  const appendReasoning = (content: string, id: string) => {
    const last = items[items.length - 1]
    if (last?.type === 'reasoning') {
      items[items.length - 1] = { ...last, content: `${last.content}${content}` }
      return
    }
    items.push({ id, type: 'reasoning', content })
  }

  const upsertTool = (event: AgentRunEvent, partial: Partial<AgentToolLog>) => {
    const id = String(event.payload.tool_log_id)
    const index = items.findIndex((item) => item.type === 'tool_call' && item.log.tool_log_id === id)
    const fallback: AgentToolLog = {
      tool_log_id: id,
      run_id: event.run_id,
      tool_name: String(event.payload.tool_name ?? ''),
      tool_args: {},
      status: 'running',
      created_at: event.created_at,
    }
    if (index >= 0) {
      const item = items[index] as TimelineToolItem
      items[index] = { ...item, log: { ...item.log, ...partial } }
      return
    }
    items.push({ id: `tool-${id}`, type: 'tool_call', log: { ...fallback, ...partial } })
  }

  events.forEach((event) => {
    lastSequence = Math.max(lastSequence, event.sequence)
    const payload = event.payload
    if (event.event_type === 'message_delta') {
      const role = payload.role === 'system' ? 'system' : 'assistant'
      const content = String(payload.content ?? '')
      if (content && role !== 'system') appendAssistant(content, event.event_id)
    }
    if (event.event_type === 'reasoning_delta') {
      const content = String(payload.content ?? '')
      if (content) appendReasoning(content, event.event_id)
    }
    if (event.event_type === 'tool_call_started') {
      upsertTool(event, {
        tool_log_id: String(payload.tool_log_id),
        run_id: event.run_id,
        tool_name: String(payload.tool_name ?? ''),
        tool_args: (payload.args as Record<string, unknown>) ?? {},
        status: String(payload.status ?? 'running'),
        created_at: event.created_at,
      })
    }
    if (event.event_type === 'tool_call_result' || event.event_type === 'tool_call_error') {
      upsertTool(event, {
        tool_name: String(payload.tool_name ?? ''),
        status: String(payload.status ?? (event.event_type === 'tool_call_error' ? 'error' : 'success')),
        output: payload.output,
        error: typeof payload.error === 'string' ? payload.error : null,
        latency_ms: typeof payload.latency_ms === 'number' ? payload.latency_ms : null,
      })
    }
    if (event.event_type === 'final_answer') {
      const answer = String(payload.answer ?? '')
      if (answer && !hasAssistantOutput) appendAssistant(answer, event.event_id)
    }
    if (event.event_type === 'run_error') {
      items.push({ id: event.event_id, type: 'system_notice', content: String(payload.error ?? 'Agent run failed') })
    }
    if (event.event_type === 'run_cancelled') {
      items.push({ id: event.event_id, type: 'system_notice', content: String(payload.reason ?? 'Agent run cancelled') })
    }
  })

  if (run.status === 'failed' && run.error && !events.some((event) => event.event_type === 'run_error')) {
    items.push({ id: `error-${run.run_id}`, type: 'system_notice', content: run.error })
  }
  if (run.status === 'cancelled' && run.error && !events.some((event) => event.event_type === 'run_cancelled')) {
    items.push({ id: `cancelled-${run.run_id}`, type: 'system_notice', content: run.error })
  }

  return { items, lastSequence, hasAssistantOutput }
}

export default function SmartRAGAgentPage() {
  const [modelId, setModelId] = useState<string | undefined>(() => readStorage(STORAGE_KEYS.selectedModelId) || undefined)
  const [input, setInput] = useState(() => readStorage(STORAGE_KEYS.draftInput))
  const [running, setRunning] = useState(false)
  const [timelineItems, setTimelineItems] = useState<TimelineItem[]>([])
  const [activeRunId, setActiveRunId] = useState<string | undefined>(() => readStorage(STORAGE_KEYS.activeRunId) || undefined)
  const [actionsOpen, setActionsOpen] = useState(false)
  const [actionSearch, setActionSearch] = useState('')
  const [actionFilter, setActionFilter] = useState<'all' | 'read_only' | 'destructive'>('all')
  const eventSourceRef = useRef<EventSource | null>(null)
  const currentRunIdRef = useRef<string | null>(null)
  const timelineScrollRef = useRef<HTMLDivElement | null>(null)
  const shouldFollowTimelineRef = useRef(true)
  const itemCounterRef = useRef(0)
  const hasAssistantOutputRef = useRef(false)
  const lastEventSequenceRef = useRef(0)
  const reconnectTimerRef = useRef<number | null>(null)
  const streamRecoveringRef = useRef(false)
  const modelsQuery = useModels()
  const actionsQuery = useAgentActions()
  const activeRunQuery = useSmartRagAgentRun(activeRunId)
  const createRun = useCreateSmartRagAgentRun()
  const cancelRun = useCancelSmartRagAgentRun()

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

  const visibleActions = useMemo(
    () =>
      (actionsQuery.data ?? []).filter((action) => {
        if (!actionMatchesSearch(action, actionSearch.trim())) return false
        if (actionFilter === 'destructive') return action.is_destructive
        if (actionFilter === 'read_only') return !action.is_destructive
        return true
      }),
    [actionFilter, actionSearch, actionsQuery.data],
  )

  useEffect(() => {
    writeStorage(STORAGE_KEYS.selectedModelId, modelId ?? '')
  }, [modelId])

  useEffect(() => {
    writeStorage(STORAGE_KEYS.draftInput, input)
  }, [input])

  useEffect(() => () => {
    eventSourceRef.current?.close()
    if (reconnectTimerRef.current != null) {
      window.clearTimeout(reconnectTimerRef.current)
    }
  }, [])

  useEffect(() => {
    const element = timelineScrollRef.current
    if (!element || !shouldFollowTimelineRef.current) return
    element.scrollTop = element.scrollHeight
  }, [timelineItems])

  const makeItemId = (prefix: string) => {
    itemCounterRef.current += 1
    return `${prefix}-${Date.now()}-${itemCounterRef.current}`
  }

  const setStoredActiveRun = (runId?: string) => {
    currentRunIdRef.current = runId ?? null
    setActiveRunId(runId)
    writeStorage(STORAGE_KEYS.activeRunId, runId ?? '')
  }

  const appendAssistantDelta = (content: string) => {
    hasAssistantOutputRef.current = true
    setTimelineItems((items) => {
      const last = items[items.length - 1]
      if (last?.type === 'assistant_message') {
        return [...items.slice(0, -1), { ...last, content: `${last.content}${content}` }]
      }
      return [...items, { id: makeItemId('assistant'), type: 'assistant_message', content }]
    })
  }

  const appendNotice = (content: string) => {
    setTimelineItems((items) => [...items, { id: makeItemId('notice'), type: 'system_notice', content }])
  }

  const upsertToolLog = (id: string, event: AgentRunEvent, partial: Partial<AgentToolLog>) => {
    setTimelineItems((items) => {
      const index = items.findIndex((item) => item.type === 'tool_call' && item.log.tool_log_id === id)
      const fallback: AgentToolLog = {
        tool_log_id: id,
        run_id: event.run_id,
        tool_name: String(event.payload.tool_name ?? ''),
        tool_args: {},
        status: 'running',
        created_at: event.created_at,
      }
      if (index >= 0) {
        const item = items[index] as TimelineToolItem
        const next = [...items]
        next[index] = { ...item, log: { ...item.log, ...partial } }
        return next
      }
      return [...items, { id: makeItemId('tool'), type: 'tool_call', log: { ...fallback, ...partial } }]
    })
  }

  const applyEvent = (event: AgentRunEvent) => {
    lastEventSequenceRef.current = Math.max(lastEventSequenceRef.current, event.sequence)
    const payload = event.payload
    if (event.event_type === 'message_delta') {
      const role = payload.role === 'system' ? 'system' : 'assistant'
      const content = String(payload.content ?? '')
      if (content && role !== 'system') {
        appendAssistantDelta(content)
      }
    }
    if (event.event_type === 'reasoning_delta') {
      const content = String(payload.content ?? '')
      if (content) {
        setTimelineItems((items) => {
          const last = items[items.length - 1]
          if (last?.type === 'reasoning') {
            return [...items.slice(0, -1), { ...last, content: `${last.content}${content}` }]
          }
          return [...items, { id: makeItemId('reasoning'), type: 'reasoning', content }]
        })
      }
    }
    if (event.event_type === 'tool_call_started') {
      const id = String(payload.tool_log_id)
      upsertToolLog(id, event, {
          tool_log_id: id,
          run_id: event.run_id,
          tool_name: String(payload.tool_name ?? ''),
          tool_args: (payload.args as Record<string, unknown>) ?? {},
          status: String(payload.status ?? 'running'),
          created_at: event.created_at,
      })
    }
    if (event.event_type === 'tool_call_result' || event.event_type === 'tool_call_error') {
      const id = String(payload.tool_log_id)
      upsertToolLog(id, event, {
        tool_name: String(payload.tool_name ?? ''),
        status: String(payload.status ?? (event.event_type === 'tool_call_error' ? 'error' : 'success')),
        output: payload.output,
        error: typeof payload.error === 'string' ? payload.error : null,
        latency_ms: typeof payload.latency_ms === 'number' ? payload.latency_ms : null,
      })
    }
    if (event.event_type === 'final_answer') {
      setRunning(false)
      setStoredActiveRun(undefined)
      const answer = String(payload.answer ?? '')
      if (answer && !hasAssistantOutputRef.current) {
        appendAssistantDelta(answer)
      }
    }
    if (event.event_type === 'run_error') {
      setRunning(false)
      setStoredActiveRun(undefined)
      appendNotice(String(payload.error ?? 'Agent run failed'))
      message.error(String(payload.error ?? 'Agent run failed'))
    }
    if (event.event_type === 'run_cancelled') {
      setRunning(false)
      setStoredActiveRun(undefined)
      appendNotice(String(payload.reason ?? 'Agent run cancelled'))
    }
  }

  const connectToRun = (runId: string, afterSequence = lastEventSequenceRef.current) => {
    if (reconnectTimerRef.current != null) {
      window.clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    eventSourceRef.current?.close()
    const params = new URLSearchParams()
    if (afterSequence > 0) {
      params.set('after_sequence', String(afterSequence))
    }
    const suffix = params.toString() ? `?${params.toString()}` : ''
    const source = new EventSource(`${API_BASE_URL}/smartrag-agent/runs/${runId}/events${suffix}`)
    eventSourceRef.current = source
    source.onopen = () => {
      streamRecoveringRef.current = false
    }
    eventTypes.forEach((eventType) => {
      source.addEventListener(eventType, (rawEvent) => {
        const parsed = JSON.parse((rawEvent as MessageEvent).data) as AgentRunEvent
        applyEvent(parsed)
        if (eventType === 'final_answer' || eventType === 'run_error' || eventType === 'run_cancelled') {
          source.close()
        }
      })
    })
    source.onerror = () => {
      source.close()
      if (currentRunIdRef.current !== runId) return
      if (!streamRecoveringRef.current) {
        streamRecoveringRef.current = true
        appendNotice('Agent event stream disconnected. Recovering run status...')
      }
      void recoverRunState(runId)
    }
  }

  const recoverRunState = async (runId: string) => {
    try {
      const run = await apiClient.get<SmartRagAgentRun>(`/smartrag-agent/runs/${runId}`)
      const rebuilt = buildTimelineFromRun(run)
      setTimelineItems(rebuilt.items)
      lastEventSequenceRef.current = rebuilt.lastSequence
      hasAssistantOutputRef.current = rebuilt.hasAssistantOutput
      if (isTerminalRun(run.status)) {
        setRunning(false)
        setStoredActiveRun(undefined)
        if (run.status === 'failed') {
          message.error(run.error ?? 'Agent run failed')
        }
        return
      }
      setRunning(true)
      reconnectTimerRef.current = window.setTimeout(() => connectToRun(run.run_id), 700)
    } catch {
      if (currentRunIdRef.current !== runId) return
      setRunning(true)
      reconnectTimerRef.current = window.setTimeout(() => connectToRun(runId), 1500)
    }
  }

  const startRun = async () => {
    const content = input.trim()
    if (!modelId || !content) return
    eventSourceRef.current?.close()
    setInput('')
    setRunning(true)
    hasAssistantOutputRef.current = false
    lastEventSequenceRef.current = 0
    shouldFollowTimelineRef.current = true
    setTimelineItems((items) => [...items, { id: makeItemId('user'), type: 'user_message', content }])
    try {
      const run = await createRun.mutateAsync({ model_id: modelId, message: content })
      setStoredActiveRun(run.run_id)
      connectToRun(run.run_id, 0)
    } catch (error) {
      setRunning(false)
      message.error(error instanceof Error ? error.message : 'Failed to start SmartRAG Agent')
    }
  }

  const stopRun = async () => {
    const runId = currentRunIdRef.current
    if (!runId) return
    try {
      await cancelRun.mutateAsync(runId)
      eventSourceRef.current?.close()
      setRunning(false)
      setStoredActiveRun(undefined)
      appendNotice('Agent run cancelled.')
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'Cancel failed')
    }
  }

  const handleTimelineScroll = () => {
    const element = timelineScrollRef.current
    if (!element) return
    const distanceToBottom = element.scrollHeight - element.scrollTop - element.clientHeight
    shouldFollowTimelineRef.current = distanceToBottom < 32
  }

  useEffect(() => {
    const run = activeRunQuery.data
    if (!run) return
    currentRunIdRef.current = run.run_id
    const rebuilt = buildTimelineFromRun(run)
    setTimelineItems(rebuilt.items)
    lastEventSequenceRef.current = rebuilt.lastSequence
    hasAssistantOutputRef.current = rebuilt.hasAssistantOutput
    if (isTerminalRun(run.status)) {
      setRunning(false)
      setStoredActiveRun(undefined)
      return
    }
    setRunning(true)
    connectToRun(run.run_id, rebuilt.lastSequence)
  }, [activeRunQuery.data])

  const renderTimelineItem = (item: TimelineItem) => {
    if (item.type === 'tool_call') {
      const log = item.log
      return (
        <div key={item.id} className="agentTimelineToolCard">
          <Collapse
            size="small"
            items={[
              {
                key: log.tool_log_id,
                label: (
                  <Space wrap>
                    <ToolOutlined />
                    <Text>{log.tool_name}</Text>
                    <Tag color={getStatusColor(log.status)}>{log.status}</Tag>
                    {log.latency_ms != null && <Text type="secondary">{log.latency_ms}ms</Text>}
                  </Space>
                ),
                children: (
                  <div className="agentToolBody">
                    <Text type="secondary">Args</Text>
                    <pre>{stringify(log.tool_args)}</pre>
                    <Text type="secondary">{log.error ? 'Error' : 'Output'}</Text>
                    <pre>{stringify(log.error ?? log.output)}</pre>
                  </div>
                ),
              },
            ]}
          />
        </div>
      )
    }

    const roleClass =
      item.type === 'user_message'
        ? 'user'
        : item.type === 'assistant_message'
          ? 'assistant'
          : item.type === 'reasoning'
            ? 'reasoning'
            : 'system'
    const label =
      item.type === 'user_message'
        ? 'You'
        : item.type === 'assistant_message'
          ? 'SmartRAG Agent'
          : item.type === 'reasoning'
            ? 'Reasoning'
            : 'System'
    return (
      <div key={item.id} className={`agentBubble ${roleClass}`}>
        <Text strong>{label}</Text>
        <Paragraph>{item.content}</Paragraph>
      </div>
    )
  }

  return (
    <div className="pageStack agentConsolePage">
      <div className="pageHeader">
        <div>
          <Title level={3}>SmartRAG Agent</Title>
          <Text type="secondary">通过 Registry tools 观察和执行材料、解析、分块、向量化、RAG 与测评操作。</Text>
        </div>
        <Space>
          <Button size="small" icon={<ToolOutlined />} loading={actionsQuery.isLoading} onClick={() => setActionsOpen(true)}>
            {actionsQuery.data?.length ?? 0} actions
          </Button>
          {running ? <Tag color="processing">running</Tag> : <Tag>idle</Tag>}
        </Space>
      </div>

      <div className="agentConsoleGrid">
        <section className="agentChatPanel">
          <div className="agentChatStream" ref={timelineScrollRef} onScroll={handleTimelineScroll}>
            {timelineItems.length === 0 ? (
              <Empty description="选择 LLM 后发送消息" />
            ) : (
              timelineItems.map(renderTimelineItem)
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
            {running ? (
              <Button danger icon={<StopOutlined />} loading={cancelRun.isPending} onClick={stopRun}>
                Stop
              </Button>
            ) : (
              <Button type="primary" icon={<SendOutlined />} loading={createRun.isPending} disabled={!modelId || !input.trim()} onClick={startRun}>
                Send
              </Button>
            )}
          </div>
        </section>
      </div>

      <Drawer
        title="Agent Actions"
        width={720}
        open={actionsOpen}
        onClose={() => setActionsOpen(false)}
      >
        <div className="agentActionToolbar">
          <Input.Search
            allowClear
            placeholder="搜索工具名、标题或描述"
            value={actionSearch}
            onChange={(event) => setActionSearch(event.target.value)}
          />
          <Segmented
            value={actionFilter}
            onChange={(value) => setActionFilter(value as 'all' | 'read_only' | 'destructive')}
            options={[
              { label: 'All', value: 'all' },
              { label: 'Read-only', value: 'read_only' },
              { label: 'Destructive', value: 'destructive' },
            ]}
          />
        </div>
        {visibleActions.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No actions" />
        ) : (
          <Collapse
            className="agentActionList"
            items={visibleActions.map((action) => ({
              key: action.name,
              label: (
                <Space direction="vertical" size={2} className="agentActionLabel">
                  <Space wrap>
                    <Text strong>{action.name}</Text>
                    <Tag color={action.is_destructive ? 'red' : 'green'}>
                      {action.is_destructive ? 'destructive' : 'read-only'}
                    </Tag>
                    <Tag>{action.permission_scope}</Tag>
                  </Space>
                  <Text type="secondary">{action.title}</Text>
                </Space>
              ),
              children: (
                <div className="agentActionBody">
                  <Text type="secondary">LLM-visible description</Text>
                  <Paragraph>{action.description}</Paragraph>
                  <Space wrap>
                    {action.tags.map((tag) => (
                      <Tag key={tag}>{tag}</Tag>
                    ))}
                    {action.resource_uri_template && <Tag color="blue">{action.resource_uri_template}</Tag>}
                  </Space>
                  <Text type="secondary">Input schema</Text>
                  <pre>{stringify(action.input_schema)}</pre>
                  <Text type="secondary">Output schema</Text>
                  <pre>{stringify(action.output_schema)}</pre>
                </div>
              ),
            }))}
          />
        )}
      </Drawer>
    </div>
  )
}
