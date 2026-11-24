import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { JsonViewer } from '@/components/shared/JsonViewer'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { PageHeader } from '@/components/shared/PageHeader'
import { Badge, Card, EmptyState, Input, Modal, Select, Skeleton, Tabs } from '@/components/ui'
import { api } from '@/lib/api'
import { fmtMs, timeAgo } from '@/lib/utils'
import type { Run } from '@/types'

const EVENT_TYPES = ['node.started', 'node.completed', 'node.failed', 'node.retrying', 'node.waiting', 'tool.called', 'llm.call', 'approval.requested', 'approval.decided', 'run.status']

function EventsTab() {
  const [f, setF] = useState({ run_id: '', event: '', node: '', status: '' })
  const [open, setOpen] = useState<any>(null)
  const runs = useQuery({ queryKey: ['runs'], queryFn: () => api.get<Run[]>('/operations', { limit: 50 }) })
  const q = useQuery({ queryKey: ['obs-events', f], queryFn: () => api.get<any[]>('/observability/events', { ...f, limit: 300 }), refetchInterval: 5000 })
  return (
    <>
      <div className="mb-4 grid gap-3 sm:grid-cols-4">
        <Select value={f.run_id} onChange={(e) => setF({ ...f, run_id: e.target.value })}><option value="">All missions</option>
          {runs.data?.map((r) => <option key={r.id} value={r.id}>{r.request.slice(0, 48)}</option>)}</Select>
        <Select value={f.event} onChange={(e) => setF({ ...f, event: e.target.value })}><option value="">All events</option>{EVENT_TYPES.map((t) => <option key={t}>{t}</option>)}</Select>
        <Input placeholder="Agent / node id" value={f.node} onChange={(e) => setF({ ...f, node: e.target.value })} />
        <Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="">Any status</option>
          {['running', 'completed', 'failed', 'retrying', 'ok', 'error'].map((s) => <option key={s}>{s}</option>)}</Select>
      </div>
      <Card className="overflow-x-auto">
        {q.isLoading ? <Skeleton className="h-64" /> : !q.data?.length ? <EmptyState title="No events match" /> : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-xs text-muted"><th className="p-3">Time</th><th>Event</th><th>Node</th><th>Status</th><th>Mission</th></tr></thead>
            <tbody>{q.data.map((e) => (
              <tr key={e.id} onClick={() => setOpen(e)} className="cursor-pointer border-b border-border/60 hover:bg-panel2">
                <td className="p-3 text-xs text-muted">{timeAgo(e.created_at)}</td><td className="font-mono text-xs">{e.event}</td>
                <td className="text-xs">{e.node_id ?? '—'}</td><td>{e.status ? <StatusBadge status={e.status} /> : '—'}</td>
                <td><Link onClick={(ev) => ev.stopPropagation()} to={`/operations/${e.run_id}`} className="text-xs text-violet">{e.run_id.slice(0, 8)}</Link></td>
              </tr>))}</tbody>
          </table>
        )}
      </Card>
      <Modal open={!!open} onClose={() => setOpen(null)} title={open?.event ?? ''} wide>{open && <JsonViewer value={open} height={360} />}</Modal>
    </>
  )
}

function ToolsTab() {
  const [open, setOpen] = useState<any>(null)
  const q = useQuery({ queryKey: ['obs-tools'], queryFn: () => api.get<any[]>('/observability/tool-calls', { limit: 300 }), refetchInterval: 8000 })
  return (
    <>
      <Card className="overflow-x-auto">
        {q.isLoading ? <Skeleton className="h-64" /> : !q.data?.length ? <EmptyState title="No tool calls yet" /> : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-xs text-muted"><th className="p-3">Tool</th><th>Result</th><th>Duration</th><th>Side effect</th><th>When</th><th>Mission</th></tr></thead>
            <tbody>{q.data.map((e) => (
              <tr key={e.id} onClick={() => setOpen(e)} className="cursor-pointer border-b border-border/60 hover:bg-panel2">
                <td className="p-3 font-mono text-xs">{e.data.tool}</td>
                <td><Badge tone={e.status === 'ok' ? 'ok' : 'bad'}>{e.status}</Badge></td><td className="text-xs">{fmtMs(e.data.duration_ms)}</td>
                <td>{e.data.side_effect ? <Badge tone="warn">yes</Badge> : <span className="text-xs text-muted">no</span>}</td>
                <td className="text-xs text-muted">{timeAgo(e.created_at)}</td>
                <td><Link onClick={(ev) => ev.stopPropagation()} to={`/operations/${e.run_id}`} className="text-xs text-violet">{e.run_id.slice(0, 8)}</Link></td>
              </tr>))}</tbody>
          </table>
        )}
      </Card>
      <Modal open={!!open} onClose={() => setOpen(null)} title="Tool call" wide>{open && <JsonViewer value={open.data} height={260} />}</Modal>
    </>
  )
}

function LlmTab() {
  const q = useQuery({ queryKey: ['obs-llm'], queryFn: () => api.get<{ model: string; calls: number; total_tokens: number; avg_latency_ms: number }[]>('/observability/llm-usage') })
  if (q.isLoading) return <Skeleton className="h-40" />
  if (!q.data?.length) return <EmptyState title="No LLM calls recorded" hint="Add GROQ_API_KEY to the backend .env. Without it, agents use deterministic fallbacks." />
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {q.data.map((m) => (
        <Card key={m.model} className="p-4"><div className="font-mono text-xs text-violet">{m.model}</div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            <div><div className="text-xl font-semibold">{m.calls}</div><div className="text-[10px] text-muted">calls</div></div>
            <div><div className="text-xl font-semibold">{m.total_tokens.toLocaleString()}</div><div className="text-[10px] text-muted">tokens</div></div>
            <div><div className="text-xl font-semibold">{fmtMs(m.avg_latency_ms)}</div><div className="text-[10px] text-muted">avg latency</div></div>
          </div></Card>
      ))}
    </div>
  )
}

export function Observatory() {
  const [tab, setTab] = useState<'events' | 'tools' | 'llm'>('events')
  return (
    <div className="mx-auto max-w-7xl p-6">
      <PageHeader title="Agent Observatory" subtitle="Execution events, tool calls, retries, failures and model usage."
        actions={<Tabs value={tab} onChange={setTab} tabs={[{ id: 'events', label: 'Events' }, { id: 'tools', label: 'Tool calls' }, { id: 'llm', label: 'LLM usage' }]} />} />
      {tab === 'events' ? <EventsTab /> : tab === 'tools' ? <ToolsTab /> : <LlmTab />}
    </div>
  )
}
