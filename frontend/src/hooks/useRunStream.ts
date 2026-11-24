import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { WS_URL } from '@/lib/api'
import { useAuth } from '@/stores/auth'
import type { RunEvent } from '@/types'

/** Live execution events. The backend replays history on connect, then streams. Reconnects with backoff. */
export function useRunStream(runId?: string) {
  const token = useAuth((s) => s.token)
  const qc = useQueryClient()
  const [events, setEvents] = useState<RunEvent[]>([])
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    if (!runId || !token) return
    setEvents([])
    let ws: WebSocket | null = null, stop = false, retry = 0
    let reconnect: ReturnType<typeof setTimeout>, debounce: ReturnType<typeof setTimeout>

    const bump = () => {
      clearTimeout(debounce)
      debounce = setTimeout(() => {
        qc.invalidateQueries({ queryKey: ['run', runId] })
        qc.invalidateQueries({ queryKey: ['graph', runId] })
        qc.invalidateQueries({ queryKey: ['approvals'] })
        qc.invalidateQueries({ queryKey: ['dashboard'] })
      }, 250)
    }
    const connect = () => {
      ws = new WebSocket(`${WS_URL}/operations/${runId}/stream?token=${encodeURIComponent(token)}`)
      ws.onopen = () => { retry = 0; setConnected(true) }
      ws.onmessage = (m) => {
        const ev: RunEvent = JSON.parse(m.data)
        if (ev.event === 'ping') return
        setEvents((p) => (p.some((e) => e.id === ev.id) ? p : [...p, ev]))
        bump()
      }
      ws.onclose = (e) => {
        setConnected(false)
        if (stop || e.code === 4401) return
        reconnect = setTimeout(connect, Math.min(1000 * 2 ** retry++, 15000))
      }
    }
    connect()
    return () => { stop = true; clearTimeout(reconnect); clearTimeout(debounce); ws?.close() }
  }, [runId, token, qc])

  return { events, connected }
}
