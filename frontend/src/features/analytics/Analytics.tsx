import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Download } from 'lucide-react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/shared/PageHeader'
import { Button, Card, EmptyState, Skeleton } from '@/components/ui'
import { useDashboard } from '@/hooks/queries'
import { api, download } from '@/lib/api'
import { fmtINR, fmtMs, fmtSecs, hasRole, timeAgo } from '@/lib/utils'
import { useAuth } from '@/stores/auth'
import type { ReportRec } from '@/types'

const tip = { contentStyle: { background: 'rgb(var(--panel))', border: '1px solid rgb(var(--border))', borderRadius: 8, fontSize: 12 } }
const axis = { tick: { fontSize: 11, fill: '#8a92ad' }, axisLine: false, tickLine: false } as const

function Kpi({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return <Card className="p-4"><div className="text-xs text-muted">{label}</div><div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>{hint && <div className="mt-0.5 text-[11px] text-muted">{hint}</div>}</Card>
}

export function Analytics() {
  const qc = useQueryClient()
  const role = useAuth((s) => s.role)
  const { data: d, isLoading } = useDashboard()
  const reports = useQuery({ queryKey: ['reports'], queryFn: () => api.get<ReportRec[]>('/reports') })
  const gen = useMutation({
    mutationFn: () => api.post('/reports', { kind: 'collection' }),
    onSuccess: () => { toast.success('Report generated'); qc.invalidateQueries({ queryKey: ['reports'] }) }, onError: (e: any) => toast.error(e.message),
  })
  const dl = (id: string, ext: 'csv' | 'pdf') => download(`/reports/${id}/${ext}`, `report-${id.slice(0, 8)}.${ext}`).catch((e) => toast.error(e.message))

  if (isLoading || !d) return <div className="space-y-4 p-6"><Skeleton className="h-28" /><Skeleton className="h-72" /></div>
  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <PageHeader title="Operations Analytics" subtitle="Workflow performance over the last 30 days." />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Kpi label="Workflows completed" value={d.tasks_completed_30d} />
        <Kpi label="Success rate" value={d.success_rate != null ? `${d.success_rate}%` : '—'} />
        <Kpi label="Approval turnaround" value={fmtSecs(d.approval_turnaround_seconds)} hint="average, human-approved" />
        <Kpi label="Avg execution" value={fmtSecs(d.avg_execution_seconds)} hint="including approval wait" />
        <Kpi label="Est. time saved" value={`${d.estimated_minutes_saved} min`} hint={`${d.emails_sent_30d} emails · estimate, not measured`} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4"><div className="mb-3 text-sm font-semibold">Workflows per day</div>
          <div className="h-64"><ResponsiveContainer><BarChart data={d.runs_per_day}><CartesianGrid vertical={false} stroke="rgba(138,146,173,.15)" />
            <XAxis dataKey="day" tickFormatter={(v) => v.slice(5)} {...axis} /><YAxis allowDecimals={false} {...axis} /><Tooltip {...tip} />
            <Bar dataKey="runs" fill="#8b5cf6" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></Card>
        <Card className="p-4"><div className="mb-3 text-sm font-semibold">Agent-level performance</div>
          <div className="h-64"><ResponsiveContainer><BarChart data={d.agent_performance}><CartesianGrid vertical={false} stroke="rgba(138,146,173,.15)" />
            <XAxis dataKey="agent" tickFormatter={(v) => String(v).replace('_agent', '')} {...axis} /><YAxis allowDecimals={false} {...axis} /><Tooltip {...tip} /><Legend />
            <Bar dataKey="executions" fill="#22d3ee" radius={[4, 4, 0, 0]} /><Bar dataKey="failures" fill="#f87171" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></Card>
      </div>
      <Card className="overflow-x-auto"><div className="border-b border-border p-4 text-sm font-semibold">Average step duration by agent</div>
        <table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted"><th className="p-3">Agent</th><th>Executions</th><th>Failures</th><th>Avg duration</th></tr></thead>
          <tbody>{d.agent_performance.map((a) => <tr key={a.agent} className="border-t border-border/60"><td className="p-3">{a.agent}</td><td>{a.executions}</td><td>{a.failures}</td><td>{fmtMs(a.avg_ms)}</td></tr>)}</tbody></table></Card>

      <Card>
        <div className="flex items-center justify-between border-b border-border p-4"><div className="text-sm font-semibold">Collection reports</div>
          {hasRole(role, 'operator') && <Button size="sm" loading={gen.isPending} onClick={() => gen.mutate()}>Generate report</Button>}</div>
        {!reports.data?.length ? <EmptyState title="No reports yet" hint="Reports are created automatically at the end of a workflow, or on demand." /> : (
          <table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted"><th className="p-3">Report</th><th>Overdue</th><th>Total outstanding</th><th>Created</th><th /></tr></thead>
            <tbody>{reports.data.map((r) => (
              <tr key={r.id} className="border-t border-border/60"><td className="p-3 font-mono text-xs">{r.id.slice(0, 8)}</td><td>{r.summary.overdue_invoice_count}</td><td>{fmtINR(r.summary.total_outstanding)}</td><td className="text-xs text-muted">{timeAgo(r.created_at)}</td>
                <td className="space-x-1 pr-3 text-right"><Button size="sm" variant="outline" onClick={() => dl(r.id, 'csv')}><Download className="h-3 w-3" />CSV</Button><Button size="sm" variant="outline" onClick={() => dl(r.id, 'pdf')}><Download className="h-3 w-3" />PDF</Button></td></tr>))}</tbody></table>
        )}
      </Card>
    </div>
  )
}
