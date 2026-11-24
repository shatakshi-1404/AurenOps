import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { PageHeader } from '@/components/shared/PageHeader'
import { Badge, Button, Card, Field, Input, Modal, Select, Skeleton, Tabs } from '@/components/ui'
import { api } from '@/lib/api'
import { ROLE_RANK, timeAgo } from '@/lib/utils'
import { useAuth } from '@/stores/auth'
import type { Policy } from '@/types'

const MODES = ['auto', 'approval', 'restricted']
const ROLES = ['viewer', 'operator', 'admin', 'owner']

function Members() {
  const qc = useQueryClient()
  const { user, role } = useAuth()
  const [open, setOpen] = useState(false)
  const [temp, setTemp] = useState<string | null>(null)
  const q = useQuery({ queryKey: ['members'], queryFn: () => api.get<{ user_id: string; email: string; full_name: string; role: string }[]>('/admin/members') })
  const refresh = () => qc.invalidateQueries({ queryKey: ['members'] })
  const setRole = useMutation({ mutationFn: (v: { id: string; role: string }) => api.patch(`/admin/members/${v.id}`, { role: v.role }), onSuccess: () => { toast.success('Role updated'); refresh() }, onError: (e: any) => { toast.error(e.message); refresh() } })
  const remove = useMutation({ mutationFn: (id: string) => api.del(`/admin/members/${id}`), onSuccess: () => { toast.success('Member removed'); refresh() }, onError: (e: any) => toast.error(e.message) })
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(z.object({ full_name: z.string().min(1, 'Required'), email: z.string().email(), role: z.enum(['viewer', 'operator', 'admin', 'owner']) })),
    defaultValues: { role: 'operator' } as any,
  })
  const myRank = ROLE_RANK[role as keyof typeof ROLE_RANK] ?? 0
  return (
    <Card>
      <div className="flex items-center justify-between border-b border-border p-4"><div className="text-sm font-semibold">Team members</div><Button size="sm" onClick={() => { setTemp(null); setOpen(true) }}>Invite</Button></div>
      {q.isLoading ? <Skeleton className="h-32" /> : (
        <table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted"><th className="p-3">Member</th><th>Role</th><th /></tr></thead>
          <tbody>{q.data?.map((m) => { const locked = m.user_id === user?.id || (ROLE_RANK[m.role as keyof typeof ROLE_RANK] ?? 0) > myRank; return (
            <tr key={m.user_id} className="border-t border-border/60">
              <td className="p-3"><div className="font-medium">{m.full_name}</div><div className="text-xs text-muted">{m.email}</div></td>
              <td><Select className="w-32" value={m.role} disabled={locked} onChange={(e) => setRole.mutate({ id: m.user_id, role: e.target.value })}>
                {ROLES.filter((r) => ROLE_RANK[r as keyof typeof ROLE_RANK] <= myRank).map((r) => <option key={r}>{r}</option>)}</Select></td>
              <td className="pr-3 text-right">{!locked && <Button size="sm" variant="danger" onClick={() => window.confirm(`Remove ${m.email}?`) && remove.mutate(m.user_id)}>Remove</Button>}</td>
            </tr>) })}</tbody></table>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Invite a teammate">
        <form className="space-y-3" onSubmit={handleSubmit(async (v: any) => {
          try { const r: any = await api.post('/auth/invite', v); setTemp(r.temporary_password ?? 'existing account'); reset(); refresh() }
          catch (e: any) { toast.error(e.message) }
        })}>
          <Field label="Name" error={errors.full_name?.message as string}><Input {...register('full_name')} /></Field>
          <Field label="Email" error={errors.email?.message as string}><Input type="email" {...register('email')} /></Field>
          <Field label="Role"><Select {...register('role')}>{ROLES.filter((r) => ROLE_RANK[r as keyof typeof ROLE_RANK] <= myRank).map((r) => <option key={r}>{r}</option>)}</Select></Field>
          {temp && <div className="rounded-lg bg-panel2 p-3 text-xs">Temporary password (share securely): <code className="text-cyan">{temp}</code></div>}
          <Button className="w-full" loading={isSubmitting}>Send invite</Button>
        </form>
      </Modal>
    </Card>
  )
}

function Policies() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['policies'], queryFn: () => api.get<Record<string, Policy>>('/admin/policies') })
  const [draft, setDraft] = useState<Record<string, Policy>>({})
  const save = useMutation({
    mutationFn: (a: string) => api.put(`/admin/policies/${a}`, draft[a]),
    onSuccess: () => { toast.success('Policy saved and audited'); qc.invalidateQueries({ queryKey: ['policies'] }) }, onError: (e: any) => toast.error(e.message),
  })
  if (q.isLoading) return <Skeleton className="h-64" />
  return (
    <Card className="overflow-x-auto">
      <div className="border-b border-border p-4 text-sm font-semibold">Approval policies</div>
      <table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted"><th className="p-3">Action</th><th>Mode</th><th>Risk</th><th>Approver role</th><th /></tr></thead>
        <tbody>{Object.entries(q.data ?? {}).map(([a, base]) => { const p = { ...base, ...draft[a] }; const dirty = !!draft[a]
          const set = (patch: Partial<Policy>) => setDraft((d) => ({ ...d, [a]: { ...base, ...d[a], ...patch } }))
          return (
            <tr key={a} className="border-t border-border/60"><td className="p-3 font-mono text-xs">{a}</td>
              <td><Select className="w-36" value={p.mode} onChange={(e) => set({ mode: e.target.value as Policy['mode'] })}>{MODES.map((m) => <option key={m}>{m}</option>)}</Select></td>
              <td><Select className="w-28" value={p.risk ?? 'medium'} onChange={(e) => set({ risk: e.target.value })}>{['low', 'medium', 'high'].map((r) => <option key={r}>{r}</option>)}</Select></td>
              <td><Select className="w-32" disabled={p.mode !== 'approval'} value={p.approver_min_role ?? 'operator'} onChange={(e) => set({ approver_min_role: e.target.value as any })}>{ROLES.map((r) => <option key={r}>{r}</option>)}</Select></td>
              <td className="pr-3 text-right"><Button size="sm" disabled={!dirty} loading={save.isPending && save.variables === a} onClick={() => save.mutate(a, { onSuccess: () => setDraft((d) => { const n = { ...d }; delete n[a]; return n }) })}>Save</Button></td></tr>) })}</tbody></table>
      <div className="border-t border-border p-3 text-xs text-muted">Refund and customer deletion can never be set to auto. The backend enforces this regardless of what is chosen here.</div>
    </Card>
  )
}

function ToolsTab() {
  const q = useQuery({ queryKey: ['tools'], queryFn: () => api.get<any[]>('/admin/tools') })
  if (q.isLoading) return <Skeleton className="h-64" />
  return (
    <Card className="overflow-x-auto"><div className="border-b border-border p-4 text-sm font-semibold">Registered tools (the only things agents can do)</div>
      <table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted"><th className="p-3">Tool</th><th>Min role</th><th>Side effect</th><th>Policy action</th><th>Description</th></tr></thead>
        <tbody>{q.data?.map((t) => <tr key={t.id} className="border-t border-border/60"><td className="p-3 font-mono text-xs">{t.name}</td><td>{t.min_role}</td>
          <td>{t.side_effect ? <Badge tone="warn">yes</Badge> : 'no'}</td><td className="text-xs text-muted">{t.policy_action ?? '—'}</td><td className="text-xs text-muted">{t.description}</td></tr>)}</tbody></table></Card>
  )
}

function AuditTab() {
  const [action, setAction] = useState('')
  const [page, setPage] = useState(0)
  const size = 25
  const q = useQuery({ queryKey: ['audit', action, page], queryFn: () => api.get<{ total: number; items: any[] }>('/audit-logs', { action, limit: size, offset: page * size }) })
  return (
    <Card className="overflow-x-auto">
      <div className="flex items-center justify-between gap-3 border-b border-border p-4"><div className="text-sm font-semibold">Audit history (append-only)</div>
        <Input className="max-w-[220px]" placeholder="Action prefix, e.g. approval" value={action} onChange={(e) => { setAction(e.target.value); setPage(0) }} /></div>
      {q.isLoading ? <Skeleton className="h-64" /> : (
        <table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted"><th className="p-3">When</th><th>Action</th><th>Resource</th><th>Details</th></tr></thead>
          <tbody>{q.data?.items.map((a) => <tr key={a.id} className="border-t border-border/60 align-top"><td className="p-3 text-xs text-muted">{timeAgo(a.created_at)}</td>
            <td className="font-mono text-xs">{a.action}</td><td className="text-xs">{a.resource_type}{a.resource_id ? ` · ${a.resource_id.slice(0, 8)}` : ''}</td>
            <td className="max-w-md truncate font-mono text-[11px] text-muted" title={JSON.stringify(a.details)}>{JSON.stringify(a.details)}</td></tr>)}</tbody></table>
      )}
      <div className="flex items-center justify-between border-t border-border p-3 text-xs text-muted">
        <span>{q.data?.total ?? 0} entries</span>
        <div className="flex gap-2"><Button size="sm" variant="outline" disabled={page === 0} onClick={() => setPage(page - 1)}>Prev</Button>
          <Button size="sm" variant="outline" disabled={(page + 1) * size >= (q.data?.total ?? 0)} onClick={() => setPage(page + 1)}>Next</Button></div>
      </div>
    </Card>
  )
}

export function Admin() {
  const [tab, setTab] = useState<'members' | 'policies' | 'tools' | 'audit'>('members')
  return (
    <div className="mx-auto max-w-6xl p-6">
      <PageHeader title="Admin & Governance" subtitle="Team, roles, approval policies, tool permissions and audit history."
        actions={<Tabs value={tab} onChange={setTab} tabs={[{ id: 'members', label: 'Members' }, { id: 'policies', label: 'Policies' }, { id: 'tools', label: 'Tools' }, { id: 'audit', label: 'Audit log' }]} />} />
      {tab === 'members' ? <Members /> : tab === 'policies' ? <Policies /> : tab === 'tools' ? <ToolsTab /> : <AuditTab />}
    </div>
  )
}
