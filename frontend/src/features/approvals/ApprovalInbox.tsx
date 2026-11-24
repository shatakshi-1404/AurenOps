import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, Inbox, Pencil, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Badge, Button, Card, EmptyState, Field, Input, Modal, Skeleton, Tabs, Textarea } from '@/components/ui'
import { ApiError, api } from '@/lib/api'
import { cn, fmtINR, hasRole, timeAgo, timeUntil } from '@/lib/utils'
import { useAuth } from '@/stores/auth'
import type { ApprovalDetail, ApprovalSummary, Draft } from '@/types'

function DraftRow({ d, ev, checked, onCheck, editable, onEdit }: {
  d: Draft; ev?: ApprovalDetail['payload']['items'][number]; checked: boolean; onCheck: () => void; editable: boolean; onEdit: () => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-lg border border-border bg-panel2">
      <div className="flex items-center gap-3 p-3">
        {d.status === 'draft' && <input type="checkbox" className="h-4 w-4 accent-violet" checked={checked} onChange={onCheck} />}
        <button onClick={() => setOpen(!open)} className="text-muted">{open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}</button>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-sm"><span className="truncate font-medium">{ev?.customer ?? d.to_email}</span>{d.edited && <Badge tone="violet">edited</Badge>}</div>
          <div className="truncate text-xs text-muted">{d.to_email}</div>
        </div>
        {ev && (
          <div className="hidden items-center gap-4 text-xs sm:flex">
            <div><div className="text-muted">Invoice</div><div>{ev.invoice_number}</div></div>
            <div><div className="text-muted">Outstanding</div><div>{fmtINR(ev.outstanding)}</div></div>
            <div><div className="text-muted">Overdue</div><div>{ev.days_overdue}d</div></div>
            <div><div className="text-muted">Prev. reminders</div><div>{ev.reminders_sent}</div></div>
            <Badge tone={ev.tier === 'high' ? 'bad' : ev.tier === 'medium' ? 'warn' : 'ok'}>{ev.tier}</Badge>
          </div>
        )}
        <StatusBadge status={d.status} />
        {editable && d.status === 'draft' && <Button size="sm" variant="ghost" onClick={onEdit}><Pencil className="h-3.5 w-3.5" /></Button>}
      </div>
      {open && (
        <div className="grid gap-3 border-t border-border p-3 md:grid-cols-2">
          {d.edited && (
            <div><div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted">Before (agent draft)</div>
              <div className="rounded-lg bg-panel p-3 text-xs"><div className="mb-2 font-medium">{d.original_subject}</div><pre className="whitespace-pre-wrap font-sans text-muted">{d.original_body}</pre></div></div>
          )}
          <div className={cn(!d.edited && 'md:col-span-2')}>
            <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted">{d.edited ? 'After (your edit)' : 'Proposed email'}</div>
            <div className="rounded-lg bg-panel p-3 text-xs"><div className="mb-2 font-medium">{d.subject}</div><pre className="whitespace-pre-wrap font-sans">{d.body}</pre></div>
          </div>
        </div>
      )}
    </div>
  )
}

function DetailPane({ id }: { id: string }) {
  const qc = useQueryClient()
  const role = useAuth((s) => s.role)
  const [sel, setSel] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState<Draft | null>(null)
  const [form, setForm] = useState({ subject: '', body: '' })
  const [rejectOpen, setRejectOpen] = useState(false)
  const [note, setNote] = useState('')

  const q = useQuery({ queryKey: ['approval', id], queryFn: () => api.get<ApprovalDetail>(`/approvals/${id}`), refetchInterval: 8000 })
  const d = q.data
  const pending = d?.status === 'pending'
  const canAct = hasRole(role, 'operator') && pending
  const evMap = useMemo(() => Object.fromEntries((d?.payload.items ?? []).map((i) => [i.email_id, i])), [d])

  useEffect(() => { if (d) setSel(new Set(d.drafts.filter((x) => x.status === 'draft').map((x) => x.id))) }, [d?.id, d?.current_payload_hash]) // eslint-disable-line

  const refresh = () => { qc.invalidateQueries({ queryKey: ['approval', id] }); qc.invalidateQueries({ queryKey: ['approvals'] }); qc.invalidateQueries({ queryKey: ['dashboard'] }) }

  const edit = useMutation({
    mutationFn: () => api.patch<ApprovalDetail>(`/approvals/${id}`, { drafts: [{ email_id: editing!.id, ...form }] }),
    onSuccess: (res) => { qc.setQueryData(['approval', id], res); setEditing(null); toast.success('Draft updated. Re-review before approving.'); refresh() },
    onError: (e: any) => toast.error(e.message),
  })
  const allIds = d?.drafts.filter((x) => x.status === 'draft').map((x) => x.id) ?? []
  const approve = useMutation({
    mutationFn: () => api.post(`/approvals/${id}/approve`, {
      payload_hash: d!.current_payload_hash, email_ids: sel.size === allIds.length ? undefined : [...sel],
    }),
    onSuccess: () => { toast.success(`Approved ${sel.size} email(s). Execution resumed.`); refresh() },
    onError: (e: any) => {
      if (e instanceof ApiError && e.code === 'stale_approval') toast.warning('The proposal changed since you opened it. Reloaded. Please re-review.')
      else toast.error(e.message)
      refresh()
    },
  })
  const reject = useMutation({
    mutationFn: () => api.post(`/approvals/${id}/reject`, { note: note || undefined }),
    onSuccess: () => { toast.success('Rejected. Nothing was sent.'); setRejectOpen(false); refresh() },
    onError: (e: any) => toast.error(e.message),
  })

  if (q.isLoading || !d) return <div className="space-y-3 p-6"><Skeleton className="h-24" /><Skeleton className="h-64" /></div>

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-6">
        <div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted"><span>#{d.id.slice(0, 8)}</span><Badge tone={d.risk === 'high' ? 'bad' : 'warn'}>{d.risk} risk</Badge><StatusBadge status={d.status} /></div>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight">{d.title}</h2>
          <p className="mt-1 text-sm text-muted">Communication Agent · <Link className="text-violet" to={`/operations/${d.run_id}`}>View execution details</Link></p>
        </div>
        <div className="grid gap-3 sm:grid-cols-4">
          {[['Emails', d.payload.email_ids.length], ['Total overdue', fmtINR(d.payload.total_outstanding)], ['Expires in', timeUntil(d.expires_at)], ['Requested', timeAgo(d.created_at)]].map(([k, v]) => (
            <Card key={k as string} className="p-3"><div className="text-xs text-muted">{k}</div><div className="mt-1 font-semibold">{v}</div></Card>
          ))}
        </div>
        <Card className="space-y-1 p-4 text-sm">
          <div className="flex items-center gap-2 font-medium"><ShieldCheck className="h-4 w-4 text-violet" />Policy</div>
          <div className="text-xs text-muted">{d.policy}</div>
          <div className="text-xs text-muted">Reason: {d.reason}</div>
          {d.decision_note && <div className="text-xs text-muted">Decision note: {d.decision_note}</div>}
        </Card>
        <div>
          <div className="mb-2 flex items-center justify-between">
            <div className="text-sm font-semibold">Proposed actions & evidence</div>
            {pending && <div className="flex gap-2 text-xs"><button className="text-violet" onClick={() => setSel(new Set(allIds))}>Select all</button><button className="text-muted" onClick={() => setSel(new Set())}>None</button></div>}
          </div>
          <div className="space-y-2">
            {d.drafts.map((x) => (
              <DraftRow key={x.id} d={x} ev={evMap[x.id]} checked={sel.has(x.id)} editable={canAct}
                onCheck={() => setSel((s) => { const n = new Set(s); n.has(x.id) ? n.delete(x.id) : n.add(x.id); return n })}
                onEdit={() => { setEditing(x); setForm({ subject: x.subject, body: x.body }) }} />
            ))}
          </div>
        </div>
      </div>

      {pending && (
        <div className="flex items-center justify-between gap-3 border-t border-border bg-panel px-6 py-3">
          <div className="text-xs text-muted">{sel.size} of {allIds.length} selected. Only the exact content you reviewed will be sent.</div>
          <div className="flex gap-2">
            <Button variant="danger" disabled={!canAct} onClick={() => setRejectOpen(true)}>Reject</Button>
            <Button variant="success" disabled={!canAct || sel.size === 0} loading={approve.isPending} onClick={() => approve.mutate()}>
              {sel.size === allIds.length ? 'Approve all' : `Approve selected (${sel.size})`}
            </Button>
          </div>
        </div>
      )}

      <Modal open={!!editing} onClose={() => setEditing(null)} title="Edit draft" wide
        footer={<><Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button><Button loading={edit.isPending} onClick={() => edit.mutate()}>Save changes</Button></>}>
        <div className="space-y-3">
          <div className="rounded-lg bg-warn/10 p-3 text-xs text-warn">Editing changes the proposal. You'll need to re-review before approving.</div>
          <Field label="Subject"><Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} /></Field>
          <Field label="Body"><Textarea rows={12} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} /></Field>
        </div>
      </Modal>
      <Modal open={rejectOpen} onClose={() => setRejectOpen(false)} title="Reject this action"
        footer={<><Button variant="ghost" onClick={() => setRejectOpen(false)}>Cancel</Button><Button variant="danger" loading={reject.isPending} onClick={() => reject.mutate()}>Reject</Button></>}>
        <Field label="Reason (optional)"><Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
      </Modal>
    </div>
  )
}

export function ApprovalInbox() {
  const { id } = useParams()
  const nav = useNavigate()
  const [tab, setTab] = useState<'pending' | 'all'>('pending')
  const list = useQuery({ queryKey: ['approvals', tab], queryFn: () => api.get<ApprovalSummary[]>('/approvals', { status: tab === 'pending' ? 'pending' : undefined }), refetchInterval: 8000 })

  useEffect(() => { if (!id && list.data?.length) nav(`/approvals/${list.data[0].id}`, { replace: true }) }, [id, list.data, nav])

  return (
    <div className="flex h-full">
      <aside className="flex w-80 shrink-0 flex-col border-r border-border">
        <div className="space-y-3 border-b border-border p-4"><div className="text-sm font-semibold">Approval Inbox</div>
          <Tabs value={tab} onChange={setTab} tabs={[{ id: 'pending', label: 'Pending' }, { id: 'all', label: 'All' }]} /></div>
        <div className="flex-1 space-y-1 overflow-y-auto p-2">
          {list.isLoading && <Skeleton className="h-20" />}
          {list.data?.map((a) => (
            <Link key={a.id} to={`/approvals/${a.id}`} className={cn('block rounded-lg border p-3', a.id === id ? 'border-violet/50 bg-violet/10' : 'border-transparent hover:bg-panel2')}>
              <div className="flex items-center justify-between"><span className="text-sm font-medium">{a.title}</span><Badge tone={a.risk === 'high' ? 'bad' : 'warn'}>{a.risk}</Badge></div>
              <div className="mt-1 text-xs text-muted">{fmtINR(a.payload.total_outstanding)} · {timeAgo(a.created_at)}</div>
              <div className="mt-2"><StatusBadge status={a.status} /></div>
            </Link>
          ))}
        </div>
      </aside>
      <section className="min-w-0 flex-1">
        {id ? <DetailPane key={id} id={id} /> : <EmptyState icon={<Inbox className="h-6 w-6" />} title="Inbox zero" hint="Proposed actions that need a human decision appear here." />}
      </section>
    </div>
  )
}
