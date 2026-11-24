import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export const cn = (...i: ClassValue[]) => twMerge(clsx(i))
export const ROLE_RANK = { viewer: 0, operator: 1, admin: 2, owner: 3 } as const
export const hasRole = (role: string | null | undefined, min: keyof typeof ROLE_RANK) =>
  !!role && ROLE_RANK[role as keyof typeof ROLE_RANK] >= ROLE_RANK[min]
export const fmtINR = (n?: number | null) => (n == null ? '—' : '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 2 }))
export const fmtMs = (ms?: number | null) => (ms == null ? '—' : ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`)
export const fmtSecs = (s?: number | null) =>
  s == null ? '—' : s < 60 ? `${Math.round(s)}s` : s < 3600 ? `${Math.round(s / 60)}m` : `${(s / 3600).toFixed(1)}h`
export const ACTIVE = ['QUEUED', 'PLANNING', 'RUNNING', 'WAITING_FOR_APPROVAL', 'APPROVED', 'EXECUTING', 'VERIFYING', 'RETRYING']
export const isActive = (s: string) => ACTIVE.includes(s)

export function timeAgo(iso?: string | null) {
  if (!iso) return '—'
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return `${Math.floor(s)}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}
export function timeUntil(iso?: string | null) {
  if (!iso) return '—'
  const s = (new Date(iso).getTime() - Date.now()) / 1000
  if (s <= 0) return 'expired'
  return s < 3600 ? `${Math.ceil(s / 60)}m` : `${Math.ceil(s / 3600)}h`
}
