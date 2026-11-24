import { useAuth } from '@/stores/auth'

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'
export const WS_URL = API_URL.replace(/^http/, 'ws')

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message) }
}

type Opts = Omit<RequestInit, 'body'> & { json?: unknown; form?: FormData; query?: Record<string, unknown> }

async function raw(path: string, opts: Opts = {}) {
  const { json, form, query, headers, ...rest } = opts
  const qs = query
    ? '?' + new URLSearchParams(
        Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== '').map(([k, v]) => [k, String(v)]),
      ).toString()
    : ''
  const token = useAuth.getState().token
  const res = await fetch(`${API_URL}${path}${qs}`, {
    ...rest,
    headers: { ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...headers },
    body: form ?? (json !== undefined ? JSON.stringify(json) : undefined),
  })
  if (!res.ok) {
    let code = 'error', msg = res.statusText
    try {
      const b = await res.json()
      code = b.error?.code ?? code
      msg = b.error?.message ?? (Array.isArray(b.detail) ? b.detail.map((d: any) => d.msg).join('; ') : b.detail ?? msg)
    } catch { /* non-json error */ }
    if (res.status === 401 && token) useAuth.getState().logout()
    throw new ApiError(res.status, code, msg)
  }
  return res
}

async function request<T>(path: string, opts: Opts = {}): Promise<T> {
  const res = await raw(path, opts)
  return ((res.headers.get('content-type') ?? '').includes('json') ? res.json() : res.text()) as Promise<T>
}

export const api = {
  get: <T>(p: string, query?: Record<string, unknown>) => request<T>(p, { query }),
  post: <T>(p: string, json?: unknown) => request<T>(p, { method: 'POST', json: json ?? {} }),
  patch: <T>(p: string, json: unknown) => request<T>(p, { method: 'PATCH', json }),
  put: <T>(p: string, json: unknown) => request<T>(p, { method: 'PUT', json }),
  del: <T>(p: string) => request<T>(p, { method: 'DELETE' }),
  upload: <T>(p: string, form: FormData) => request<T>(p, { method: 'POST', form }),
}

export async function download(path: string, filename: string) {
  const res = await raw(path)
  const url = URL.createObjectURL(await res.blob())
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  a.click()
  URL.revokeObjectURL(url)
}
