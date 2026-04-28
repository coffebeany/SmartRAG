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
    throw new ApiError(response.status, (payload as { detail?: string }).detail ?? response.statusText, payload)
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
