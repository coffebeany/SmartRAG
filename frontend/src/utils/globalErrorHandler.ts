import type { MessageInstance } from 'antd/es/message/interface'

let messageApi: MessageInstance | null = null
const recentErrors = new Map<string, number>()
const DEDUP_WINDOW_MS = 2000

export function setGlobalMessageApi(api: MessageInstance) {
  messageApi = api
}

export function showGlobalError(msg: string) {
  if (!messageApi) return
  const now = Date.now()
  const last = recentErrors.get(msg)
  if (last && now - last < DEDUP_WINDOW_MS) return
  recentErrors.set(msg, now)
  if (recentErrors.size > 50) {
    for (const [key, ts] of recentErrors) {
      if (now - ts > DEDUP_WINDOW_MS) recentErrors.delete(key)
    }
  }
  messageApi.error(msg)
}
