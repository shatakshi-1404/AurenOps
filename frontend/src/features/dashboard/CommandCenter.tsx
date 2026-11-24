import { useEffect, useState, type ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import { ArrowRight, Bot, CheckCircle2, Gauge, Inbox, ShieldCheck, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Badge, Button, Card, Modal, Skeleton, Textarea } from '@/components/ui'
import { useDashboard } from '@/hooks/queries'
import { api } from '@/lib/api'
import { cn, fmtINR, hasRole, isActive, timeAgo } from '@/lib/utils'
import { useAuth } from '@/stores/auth'
import type { Agent, ApprovalSummary, Graph, Plan, Run } from '@/types'

const SUGGESTED = [
  'Find all overdue invoices, prepare personalized follow-up emails and generate a collection report.',
  'Find overdue invoices older than 30 days and draft reminder emails.',
  'Generate a collection report of all overdue invoices.',
  'Show overdue invoices above 50000 rupees.',
]

const greeting = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening' }

function Stat({ label, value, hint, icon }: { label: string; value: ReactNode; hint: string; icon: ReactNode }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between text-xs text-muted"><span className="uppercase tracking-wider">{label}</span>{icon}</div>
      <div className="mt-2 text-3xl font-semibold tabular-nums">{value}</div>
      <div className="mt-1 text-xs text-muted">{hint}</div>
    </Card>
  )
}

function Pipeline({ runId }: { runId: string }) {
  const { data } = useQuery({
    queryKey: ['graph', runId], queryFn: () => api.get<Graph>(`/operations/${runId}/graph`),
    refetchInterval: (q) => (q.state.data && isActive(q.state.data.status) ? 3000 : false),
  })
  if (!data) return <Skeleton className="h-48" />
  return (
    <ol className="space-y-1">
      {data.nodes.map((n, i) => (
        <li key={n.id} className="flex items-center gap-3 rounded-lg px-2 py-2">
          <span className={cn('grid h-6 w-6 shrink-0 place-items-center rounded-full border text-[10px]',
            n.status === 'completed' ? 'border-ok/40 bg-ok/15 text-ok' : n.status === 'running' ? 'border-cyan/40 bg-cyan/15 text-cyan'
              : n.status === 'waiting_approval' ? 'border-warn/40 bg-warn/15 text-warn' : n.status === 'failed' ? 'border-bad/40 bg-bad/15 text-bad' : 'text-muted')}>{i + 1}</span>
          <div className="min-w-0 flex-1"><div className="truncate text-sm">{n.label}</div><div className="text-xs text-muted">{n.agent}</div></div>
          <StatusBadge status={n.status} />
        </li>
      ))}
    </ol>
  )
}

export function CommandCenter() {
  const nav = useNavigate()
  const loc = useLocation()
  const { user, role } = useAuth()
  const canRun = hasRole(role, 'operator')
  const [text, setText] = useState('')
  const [plan, setPlan] = useState<Plan | null>(null)
  const dash = useDashboard()
  const agents = useQuery({ queryKey: ['agents'], queryFn: () => api.get<Agent[]>('/agents') })
  const pending = useQuery({ queryKey: ['approvals', 'pending'], queryFn: () => api.get<ApprovalSummary[]>('/approvals', { status: 'pending' }), refetchInterval: 8000 })

  useEffect(() => { const p = (loc.state as any)?.prompt; if (p) setText(p) }, [loc.state])

  const preview = useMutation({ mutationFn: () => api.post<Plan>('/operations/preview', { request: text }), onSuccess: setPlan, onError: (e: any) => toast.error(e.message) })
  const submit = useMutation({
    mutationFn: () => api.post<Run>('/operations', { request: text }),
    onSuccess: (r) => { toast.success('Mission started'); nav(`/operations/${r.id}`) },
    onError: (e: any) => toast.error(e.message),
  })

  const d = dash.data
  const latest = d?.recent_runs?.[0]
  const perf = Object.fromEntries((d?.agent_performance ?? []).map((a) => [a.agent, a]))

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <div>
        <div className="text-xs font-medium uppercase tracking-[0.2em] text-violet">Operations Command Center</div>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{greeting()}, {user?.full_name?.split(' ')[0]}. What needs to get done?</h1>
      </div>

      <Card className="p-4">
        <div className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-muted"><Sparkles className="h-3.5 w-3.5 text-violet" />Natural language command</div>
        <Textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} disabled={!canRun}
          placeholder={canRun ? 'Find overdue invoices, draft client reminders and prepare a collection report.' : 'Your role is read-only (viewer).'} />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            {SUGGESTED.map((s) => (
              <button key={s} disabled={!canRun} onClick={() => setText(s)}
                className="max-w-[260px] truncate rounded-full border border-border bg-panel2 px-3 py-1 text-xs text-muted hover:text-fg disabled:opacity-50">{s}</button>
            ))}
          </div>
          <Button disabled={!canRun || text.trim().length < 5} loading={preview.isPending} onClick={() => preview.mutate()}>Preview plan <ArrowRight className="h-4 w-4" /></Button>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {dash.isLoading ? Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />) : (<>
          <Stat label="Active agents" value={String(d?.active_agents ?? 0).padStart(2, '0')} hint={`${d?.runs_in_flight ?? 0} missions in flight`} icon={<Bot className="h-4 w-4" />} />
          <Stat label="Pending approvals" value={String(d?.pending_approvals ?? 0).padStart(2, '0')} hint="Human review needed" icon={<Inbox className="h-4 w-4" />} />
          <Stat label="Tasks completed" value={d?.tasks_completed_30d ?? 0} hint="Last 30 days" icon={<CheckCircle2 className="h-4 w-4" />} />
          <Stat label="Success rate" value={d?.success_rate != null ? `${d.success_rate}%` : '—'} hint="Completed vs failed" icon={<Gauge className="h-4 w-4" />} />
        </>)}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-4 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-semibold">Live execution pipeline</div>
            {latest && <Link to={`/operations/${latest.id}`} className="text-xs text-violet">Open Mission Canvas →</Link>}
          </div>
          {latest ? (<>
            <div className="mb-2 flex items-center gap-2"><StatusBadge status={latest.status} /><span className="truncate text-xs text-muted">{latest.request}</span></div>
            <Pipeline runId={latest.id} />
          </>) : <div className="py-10 text-center text-sm text-muted">No missions yet. Submit your first command above.</div>}
        </Card>

        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between text-sm font-semibold">Pending approvals<Link to="/approvals" className="text-xs font-normal text-violet">View all</Link></div>
          {pending.data?.length ? pending.data.slice(0, 3).map((a) => (
            <Link key={a.id} to={`/approvals/${a.id}`} className="mb-2 block rounded-lg border border-border bg-panel2 p-3 hover:border-violet/50">
              <div className="flex items-center justify-between"><span className="text-sm font-medium">{a.title}</span><Badge tone={a.risk === 'high' ? 'bad' : 'warn'}>{a.risk}</Badge></div>
              <div className="mt-1 text-xs text-muted">{fmtINR(a.payload.total_outstanding)} outstanding · {timeAgo(a.created_at)}</div>
            </Link>
          )) : <div className="py-6 text-center text-xs text-muted">Nothing awaiting review</div>}
        </Card>

        <Card className="p-4">
          <div className="mb-3 text-sm font-semibold">Agent status</div>
          <div className="space-y-2">
            {agents.data?.map((a) => (
              <div key={a.id} className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2"><span className={cn('h-2 w-2 rounded-full', a.enabled ? 'bg-ok' : 'bg-muted')} />{a.name}</span>
                <span className="text-xs text-muted">{perf[a.key]?.executions ?? 0} runs</span>
              </div>
            )) ?? <Skeleton className="h-32" />}
          </div>
        </Card>

        <Card className="p-4">
          <div className="mb-3 text-sm font-semibold">Missions per day (30d)</div>
          <div className="h-36">
            <ResponsiveContainer>
              <BarChart data={d?.runs_per_day ?? []}>
                <XAxis dataKey="day" tickFormatter={(v) => v.slice(5)} tick={{ fontSize: 10, fill: '#8a92ad' }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: 'rgb(var(--panel))', border: '1px solid rgb(var(--border))', borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="runs" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-4">
          <div className="mb-3 text-sm font-semibold">Recent execution history</div>
          <div className="space-y-1">
            {d?.recent_runs.slice(0, 5).map((r) => (
              <Link key={r.id} to={`/operations/${r.id}`} className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-panel2">
                <span className="truncate text-xs">{r.request}</span><StatusBadge status={r.status} />
              </Link>
            ))}
          </div>
        </Card>
      </div>

      <Modal open={!!plan} onClose={() => setPlan(null)} title="Execution plan preview"
        footer={<>
          <Button variant="ghost" onClick={() => setPlan(null)}>Cancel</Button>
          <Button disabled={plan?.intent === 'unknown'} loading={submit.isPending} onClick={() => submit.mutate()}>Run workflow</Button>
        </>}>
        {plan && (
          <div className="space-y-4">
            <div className="flex items-center gap-2"><Badge tone={plan.intent === 'unknown' ? 'bad' : 'violet'}>{plan.intent.replace('_', ' ')}</Badge><span className="text-xs text-muted">classified by {plan.source}</span></div>
            {plan.intent === 'unknown' ? (
              <p className="rounded-lg bg-bad/10 p-3 text-sm text-bad">This request doesn't match a supported workflow. Try asking about overdue invoices, reminders or a collection report.</p>
            ) : (<>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="rounded-lg bg-panel2 p-2"><div className="text-muted">Min days overdue</div><div className="font-semibold">{plan.params.min_days_overdue}</div></div>
                <div className="rounded-lg bg-panel2 p-2"><div className="text-muted">Min amount</div><div className="font-semibold">{fmtINR(plan.params.min_amount)}</div></div>
                <div className="rounded-lg bg-panel2 p-2"><div className="text-muted">Max drafts</div><div className="font-semibold">{plan.params.max_drafts}</div></div>
              </div>
              <ol className="space-y-2">
                {plan.steps.map((s, i) => (
                  <li key={s.key} className="flex gap-3 text-sm"><span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-panel2 text-[10px] text-muted">{i + 1}</span>
                    <span><span className="font-medium">{s.description}</span> <span className="text-xs text-muted">· {s.agent}</span></span></li>
                ))}
              </ol>
              {plan.steps.some((s) => s.key === 'approval_gate') && (
                <div className="flex items-start gap-2 rounded-lg bg-warn/10 p-3 text-xs text-warn"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />No email is sent until a human approves the exact drafts.</div>
              )}
            </>)}
          </div>
        )}
      </Modal>
    </div>
  )
}
