import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Background, Controls, MiniMap, ReactFlow, useEdgesState, useNodesState, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Ban, Play, RotateCw, Workflow } from 'lucide-react'
import { toast } from 'sonner'
import { JsonViewer } from '@/components/shared/JsonViewer'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Badge, Button, EmptyState, Skeleton, Tabs } from '@/components/ui'
import { useRunStream } from '@/hooks/useRunStream'
import { api } from '@/lib/api'
import { cn, fmtMs, hasRole, isActive, timeAgo } from '@/lib/utils'
import { useAuth } from '@/stores/auth'
import type { Graph, Run, RunDetail, RunEvent } from '@/types'
import { AgentNode } from './AgentNode'

const nodeTypes = { agent: AgentNode }

const EVENT_STATUS: Record<string, string> = {
  'node.started': 'running', 'node.completed': 'completed', 'node.failed': 'failed',
  'node.waiting': 'waiting_approval', 'node.retrying': 'retrying',
}
function replay(events: RunEvent[], upto: number) {
  const m: Record<string, string> = {}
  events.slice(0, upto + 1).forEach((e) => { if (e.node_id && EVENT_STATUS[e.event]) m[e.node_id] = EVENT_STATUS[e.event] })
  return m
}

function RunRail({ activeId }: { activeId?: string }) {
  const { data, isLoading } = useQuery({ queryKey: ['runs'], queryFn: () => api.get<Run[]>('/operations', { limit: 50 }), refetchInterval: 5000 })
  return (
    <aside className="hidden w-72 shrink-0 flex-col border-r border-border md:flex">
      <div className="border-b border-border px-4 py-3 text-sm font-semibold">Missions</div>
      <div className="flex-1 space-y-1 overflow-y-auto p-2">
        {isLoading && <Skeleton className="h-20" />}
        {data?.map((r) => (
          <Link key={r.id} to={`/operations/${r.id}`}
            className={cn('block rounded-lg border p-3 transition', r.id === activeId ? 'border-violet/50 bg-violet/10' : 'border-transparent hover:bg-panel2')}>
            <div className="line-clamp-2 text-xs">{r.request}</div>
            <div className="mt-2 flex items-center justify-between"><StatusBadge status={r.status} /><span className="text-[10px] text-muted">{timeAgo(r.created_at)}</span></div>
          </Link>
        ))}
        {data?.length === 0 && <div className="p-6 text-center text-xs text-muted">No missions yet</div>}
      </div>
    </aside>
  )
}

function MissionCanvas({ id }: { id: string }) {
  const nav = useNavigate()
  const qc = useQueryClient()
  const role = useAuth((s) => s.role)
  const { events: live, connected } = useRunStream(id)
  const [selected, setSelected] = useState<string | null>(null)
  const [panel, setPanel] = useState<'inspector' | 'timeline' | 'playback'>('inspector')
  const [playIdx, setPlayIdx] = useState<number | null>(null)
  const [ioTab, setIoTab] = useState<'input' | 'output'>('output')

  const run = useQuery({ queryKey: ['run', id], queryFn: () => api.get<RunDetail>(`/operations/${id}`), refetchInterval: (q) => (q.state.data && isActive(q.state.data.status) ? 4000 : false) })
  const graph = useQuery({ queryKey: ['graph', id], queryFn: () => api.get<Graph>(`/operations/${id}/graph`), refetchInterval: (q) => (q.state.data && isActive(q.state.data.status) ? 4000 : false) })
  const rest = useQuery({
    queryKey: ['events', id], queryFn: async () => (await api.get<any[]>(`/operations/${id}/events`)).map((e) => ({ ...e, timestamp: e.created_at }) as RunEvent),
  })

  const events = useMemo(() => {
    const map = new Map<string, RunEvent>()
    ;[...(rest.data ?? []), ...live].forEach((e) => map.set(e.id, e))
    return [...map.values()].sort((a, b) => a.timestamp.localeCompare(b.timestamp))
  }, [rest.data, live])

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  useEffect(() => {
    if (!graph.data) return
    const override = playIdx != null ? replay(events, playIdx) : null
    setNodes((prev) => graph.data!.nodes.map((n, i) => {
      const old = prev.find((p) => p.id === n.id)
      const status = override ? (n.id === 'user_instruction' ? 'completed' : override[n.id] ?? 'pending') : n.status
      return { id: n.id, type: 'agent', position: old?.position ?? { x: i * 250, y: i % 2 ? 110 : 0 }, data: { ...n, status }, selected: n.id === selected }
    }))
    setEdges(graph.data.edges.map((e) => ({ ...e, animated: playIdx != null ? false : e.animated, style: { strokeWidth: 2 } })))
  }, [graph.data, playIdx, events, selected, setNodes, setEdges])

  const act = (path: string, ok: string) => ({
    mutationFn: () => api.post(path),
    onSuccess: () => { toast.success(ok); qc.invalidateQueries({ queryKey: ['run', id] }); qc.invalidateQueries({ queryKey: ['graph', id] }); qc.invalidateQueries({ queryKey: ['runs'] }) },
    onError: (e: any) => toast.error(e.message),
  })
  const cancel = useMutation(act(`/operations/${id}/cancel`, 'Mission cancelled'))
  const retry = useMutation(act(`/operations/${id}/retry`, 'Retrying from last checkpoint'))

  const r = run.data
  const node = r?.nodes.find((n) => n.node_key === selected)
  const pendingApproval = r?.approvals.find((a) => a.status === 'pending')
  const canOperate = hasRole(role, 'operator')

  if (run.isLoading) return <div className="flex-1 p-6"><Skeleton className="h-full" /></div>
  if (!r) return <EmptyState title="Mission not found" />

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2"><StatusBadge status={r.status} />
            <span className={cn('flex items-center gap-1 text-[10px]', connected ? 'text-ok' : 'text-muted')}><span className={cn('h-1.5 w-1.5 rounded-full', connected ? 'bg-ok' : 'bg-muted')} />{connected ? 'Live' : 'Offline'}</span>
            <span className="text-[10px] text-muted">{r.token_usage} tokens</span></div>
          <div className="mt-1 max-w-2xl truncate text-sm">{r.request}</div>
        </div>
        <div className="flex gap-2">
          {pendingApproval && <Button size="sm" onClick={() => nav(`/approvals/${pendingApproval.id}`)}>Review approval</Button>}
          {canOperate && r.status === 'FAILED' && <Button size="sm" variant="outline" loading={retry.isPending} onClick={() => retry.mutate()}><RotateCw className="h-3.5 w-3.5" />Retry failed step</Button>}
          {canOperate && isActive(r.status) && <Button size="sm" variant="danger" loading={cancel.isPending} onClick={() => cancel.mutate()}><Ban className="h-3.5 w-3.5" />Cancel</Button>}
        </div>
      </div>
      {r.error && <div className="border-b border-bad/30 bg-bad/10 px-5 py-2 text-xs text-bad">{r.error}</div>}

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div className="h-[55vh] min-h-[340px] flex-1 lg:h-auto">
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            onNodeClick={(_, n) => { setSelected(n.id); setPanel('inspector') }} onPaneClick={() => setSelected(null)}
            fitView fitViewOptions={{ padding: 0.2 }} minZoom={0.2} proOptions={{ hideAttribution: true }} nodesConnectable={false}>
            <Background gap={22} color="rgba(138,146,173,0.18)" />
            <Controls showInteractive={false} />
            <MiniMap pannable zoomable nodeColor={() => '#8b5cf6'} maskColor="rgba(0,0,0,0.5)" />
          </ReactFlow>
        </div>

        <div className="flex w-full flex-col border-t border-border lg:w-[400px] lg:border-l lg:border-t-0">
          <div className="border-b border-border p-3">
            <Tabs value={panel} onChange={setPanel} tabs={[{ id: 'inspector', label: 'Inspector' }, { id: 'timeline', label: `Timeline (${events.length})` }, { id: 'playback', label: 'Playback' }]} />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {panel === 'inspector' && (!node ? (
              <div className="py-10 text-center text-xs text-muted">{selected ? 'This step has not started yet.' : 'Select a node to inspect its input, output and errors.'}</div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between"><div className="text-sm font-semibold">{node.node_key}</div><StatusBadge status={node.status} /></div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div className="rounded-lg bg-panel2 p-2"><div className="text-muted">Agent</div><div className="truncate">{node.agent_key}</div></div>
                  <div className="rounded-lg bg-panel2 p-2"><div className="text-muted">Attempts</div><div>{node.attempts}</div></div>
                  <div className="rounded-lg bg-panel2 p-2"><div className="text-muted">Duration</div><div>{fmtMs(node.duration_ms)}</div></div>
                </div>
                {node.error && <div className="rounded-lg bg-bad/10 p-3 text-xs text-bad">{node.error}</div>}
                <Tabs value={ioTab} onChange={setIoTab} tabs={[{ id: 'input', label: 'Input JSON' }, { id: 'output', label: 'Output JSON' }]} />
                <JsonViewer value={ioTab === 'input' ? node.input : node.output} height={300} />
              </div>
            ))}

            {panel === 'timeline' && (
              <ol className="space-y-2">
                {events.filter((e) => e.event !== 'ping').map((e) => (
                  <li key={e.id} className="rounded-lg border border-border bg-panel2 p-2.5 text-xs">
                    <div className="flex items-center justify-between"><span className="font-medium">{e.event}</span><span className="text-[10px] text-muted">{new Date(e.timestamp).toLocaleTimeString()}</span></div>
                    <div className="mt-0.5 flex gap-2 text-muted">{e.node_id && <span>{e.node_id}</span>}{e.status && <span>{e.status}</span>}
                      {e.data?.duration_ms != null && <span>{fmtMs(e.data.duration_ms)}</span>}{e.data?.tool && <span>tool: {e.data.tool}</span>}</div>
                    {e.data?.error && <div className="mt-1 text-bad">{String(e.data.error)}</div>}
                  </li>
                ))}
              </ol>
            )}

            {panel === 'playback' && (
              <div className="space-y-4">
                <p className="text-xs text-muted">Scrub through the recorded events to replay how this mission executed.</p>
                <input type="range" className="w-full accent-violet" min={0} max={Math.max(events.length - 1, 0)} value={playIdx ?? Math.max(events.length - 1, 0)}
                  onChange={(e) => setPlayIdx(Number(e.target.value))} />
                <div className="flex items-center justify-between text-xs">
                  <span>{playIdx != null && events[playIdx] ? `${playIdx + 1}/${events.length}: ${events[playIdx].event}` : 'Showing live state'}</span>
                  <Button size="sm" variant="outline" onClick={() => setPlayIdx(null)}><Play className="h-3 w-3" />Live</Button>
                </div>
                {playIdx != null && events[playIdx] && <JsonViewer value={events[playIdx]} height={220} />}
              </div>
            )}
          </div>
          {r.result && panel === 'inspector' && !selected && (
            <div className="border-t border-border p-4">
              <div className="mb-2 text-xs font-semibold">Result</div>
              <div className="flex flex-wrap gap-2">
                <Badge tone="ok">{r.result.sent ?? 0} sent</Badge><Badge>{r.result.drafts ?? 0} drafts</Badge>
                {!!r.result.failed && <Badge tone="bad">{r.result.failed} failed</Badge>}
                {!!r.result.unknown && <Badge tone="warn">{r.result.unknown} unknown</Badge>}
                {r.result.report_id && <Link to="/analytics" className="text-xs text-violet">View report →</Link>}
              </div>
              {r.result.analysis && <p className="mt-2 text-xs text-muted">{r.result.analysis}</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function OperationsPage() {
  const { id } = useParams()
  return (
    <div className="flex h-full">
      <RunRail activeId={id} />
      {id ? <MissionCanvas key={id} id={id} /> : (
        <div className="flex flex-1 items-center justify-center">
          <EmptyState icon={<Workflow className="h-6 w-6" />} title="Select a mission" hint="Pick a mission from the list, or submit a new command from the Command Center to watch agents work in real time." />
        </div>
      )}
    </div>
  )
}
