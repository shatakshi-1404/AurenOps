import { Badge, type Tone } from '@/components/ui'

const TONES: Record<string, Tone> = {
  completed: 'ok', COMPLETED: 'ok', sent: 'ok', approved: 'ok', ready: 'ok', connected: 'ok', low: 'ok',
  running: 'cyan', RUNNING: 'cyan', PLANNING: 'cyan', EXECUTING: 'cyan', VERIFYING: 'cyan', APPROVED: 'cyan',
  processing: 'cyan', sending: 'cyan',
  waiting_approval: 'warn', WAITING_FOR_APPROVAL: 'warn', retrying: 'warn', RETRYING: 'warn', expired: 'warn', medium: 'warn',
  failed: 'bad', FAILED: 'bad', rejected: 'bad', REJECTED: 'bad', invalidated: 'bad', high: 'bad',
}
const LIVE = ['running', 'RUNNING', 'PLANNING', 'EXECUTING', 'VERIFYING', 'processing', 'sending', 'WAITING_FOR_APPROVAL', 'waiting_approval']

export function StatusBadge({ status }: { status: string }) {
  const label = status.replace(/_/g, ' ').toLowerCase()
  return (
    <Badge tone={TONES[status] ?? 'neutral'}>
      {LIVE.includes(status) && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
      {label}
    </Badge>
  )
}
