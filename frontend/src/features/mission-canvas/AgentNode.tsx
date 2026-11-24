import { Handle, Position, type NodeProps } from '@xyflow/react'
import { AlertTriangle, CheckCircle2, CircleDashed, Loader2, PauseCircle, RotateCw } from 'lucide-react'
import { cn, fmtMs } from '@/lib/utils'

const ICON: Record<string, any> = {
  completed: <CheckCircle2 className="h-4 w-4 text-ok" />, running: <Loader2 className="h-4 w-4 animate-spin text-cyan" />,
  failed: <AlertTriangle className="h-4 w-4 text-bad" />, waiting_approval: <PauseCircle className="h-4 w-4 text-warn" />,
  retrying: <RotateCw className="h-4 w-4 animate-spin text-warn" />, pending: <CircleDashed className="h-4 w-4 text-muted" />,
}
const RING: Record<string, string> = {
  completed: 'border-ok/40', running: 'border-cyan/60 shadow-[0_0_24px_-6px] shadow-cyan/50', failed: 'border-bad/60',
  waiting_approval: 'border-warn/60 shadow-[0_0_24px_-6px] shadow-warn/40', retrying: 'border-warn/50', pending: 'border-border',
}

export function AgentNode({ data, selected }: NodeProps) {
  const d = data as { label: string; agent: string; status: string; duration_ms: number | null; attempts: number }
  return (
    <div className={cn('w-[210px] rounded-xl border bg-panel p-3 transition', RING[d.status] ?? 'border-border', selected && 'ring-2 ring-violet')}>
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-muted" />
      <div className="flex items-center justify-between"><span className="text-[10px] font-medium uppercase tracking-wider text-muted">{d.agent}</span>{ICON[d.status] ?? ICON.pending}</div>
      <div className="mt-1 line-clamp-2 text-sm font-medium leading-snug">{d.label}</div>
      <div className="mt-2 flex justify-between text-[10px] text-muted">
        <span>{d.status.replace('_', ' ')}</span>
        <span>{d.attempts > 1 ? `${d.attempts} attempts · ` : ''}{fmtMs(d.duration_ms)}</span>
      </div>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-muted" />
    </div>
  )
}
