export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'

export class ApiError extends Error {
  status: number
  payload: unknown

  constructor(status: number, message: string, payload: unknown) {
    super(message)
    this.status = status
    this.payload = payload
  }
}

function asString(value: unknown): string {
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return ''
}

function extractErrorMessage(payload: unknown, statusText: string, status: number): string {
  const fallback = asString(statusText) || `请求失败 (${status})`
  if (!payload || typeof payload !== 'object') return fallback
  const detail = (payload as { detail?: unknown }).detail
  const direct = asString(detail)
  if (direct) return direct
  if (Array.isArray(detail)) {
    const joined = detail
      .map((item) => {
        const msg = asString((item as { msg?: unknown })?.msg)
        if (msg) return msg
        const text = asString(item)
        if (text) return text
        try {
          return JSON.stringify(item)
        } catch {
          return ''
        }
      })
      .filter(Boolean)
      .join('; ')
    if (joined) return joined
  }
  try {
    const compact = JSON.stringify(payload)
    return compact && compact !== '{}' ? compact : fallback
  } catch {
    return fallback
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: isFormData ? init?.headers : {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new ApiError(response.status, extractErrorMessage(payload, response.statusText, response.status), payload)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body ?? {}) }),
  postForm: <T>(path: string, body: FormData) =>
    request<T>(path, { method: 'POST', body, headers: {} }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
