import { useAuth } from '@/stores/auth'

const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace(/\/$/, '')
  .replace(/\/api\/v1$/, '');

export const API_URL = `${BASE_URL}/api/v1`;
export const WS_URL = API_URL.replace(/^http/, 'ws');

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

type Opts = Omit<RequestInit, 'body'> & {
  json?: unknown;
  form?: FormData;
  query?: Record<string, unknown>;
};

async function raw(path: string, opts: Opts = {}) {
  const { json, form, query, headers, ...rest } = opts;

  const qs = query
    ? "?" +
      new URLSearchParams(
        Object.entries(query)
          .filter(([, v]) => v !== undefined && v !== null && v !== "")
          .map(([k, v]) => [k, String(v)])
      ).toString()
    : "";

  const token = useAuth.getState().token;

  const url = `${API_URL}${path}${qs}`;

  const res = await fetch(url, {
    ...rest,
    headers: {
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: form ?? (json !== undefined ? JSON.stringify(json) : undefined),
  });

  if (!res.ok) {
    let code = "error";
    let msg = res.statusText;

    try {
      const b = await res.json();
      code = b.error?.code ?? code;
      msg =
        b.error?.message ??
        (Array.isArray(b.detail)
          ? b.detail.map((d: any) => d.msg).join("; ")
          : b.detail ?? msg);
    } catch {}

    if (res.status === 401 && token) {
      useAuth.getState().logout();
    }

    throw new ApiError(res.status, code, msg);
  }

  const contentType = res.headers.get("content-type") ?? "";
  return contentType.includes("application/json")
    ? res.json()
    : res.text();
}

export const api = {
  get: <T>(p: string, query?: Record<string, unknown>) =>
    raw(p, { query }) as Promise<T>,

  post: <T>(p: string, json?: unknown) =>
    raw(p, { method: "POST", json: json ?? {} }) as Promise<T>,

  patch: <T>(p: string, json: unknown) =>
    raw(p, { method: "PATCH", json }) as Promise<T>,

  put: <T>(p: string, json: unknown) =>
    raw(p, { method: "PUT", json }) as Promise<T>,

  del: <T>(p: string) =>
    raw(p, { method: "DELETE" }) as Promise<T>,

  upload: <T>(p: string, form: FormData) =>
    raw(p, { method: "POST", form }) as Promise<T>,
};

export async function download(path: string, filename: string) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${useAuth.getState().token}`,
    },
  });

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();

  URL.revokeObjectURL(url);
}