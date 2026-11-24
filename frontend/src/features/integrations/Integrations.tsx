import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, HardDrive, Mail, Plug, Users } from 'lucide-react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button, Card, EmptyState, Field, Input, Modal, Select, Skeleton, Textarea } from '@/components/ui'
import { api } from '@/lib/api'
import { hasRole, timeAgo } from '@/lib/utils'
import { useAuth } from '@/stores/auth'
import type { IntegrationRec } from '@/types'

const ICON: Record<string, any> = { crm: Users, email: Mail, database: Database, storage: HardDrive }
const jsonStr = z.string().refine((s) => { if (!s.trim()) return true; try { JSON.parse(s); return true } catch { return false } }, 'Must be valid JSON')
const schema = z.object({ kind: z.enum(['crm', 'email', 'database', 'storage']), name: z.string().min(2), provider: z.string().min(1), config: jsonStr })

export function Integrations() {
  const qc = useQueryClient()
  const role = useAuth((s) => s.role)
  const [open, setOpen] = useState(false)
  const [rotate, setRotate] = useState<IntegrationRec | null>(null)
  const [cfg, setCfg] = useState('{}')
  const list = useQuery({ queryKey: ['integrations'], queryFn: () => api.get<IntegrationRec[]>('/integrations') })
  const refresh = () => qc.invalidateQueries({ queryKey: ['integrations'] })
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(schema), defaultValues: { kind: 'email', provider: 'mock', config: '{}' } as any })

  const health = useMutation({ mutationFn: (id: string) => api.post(`/integrations/${id}/health`), onSuccess: () => { toast.success('Health check passed'); refresh() }, onError: (e: any) => toast.error(e.message) })
  const del = useMutation({ mutationFn: (id: string) => api.del(`/integrations/${id}`), onSuccess: () => { toast.success('Removed'); refresh() }, onError: (e: any) => toast.error(e.message) })
  const doRotate = useMutation({
    mutationFn: () => api.post(`/integrations/${rotate!.id}/rotate`, { config: JSON.parse(cfg || '{}') }),
    onSuccess: () => { toast.success('Credentials rotated'); setRotate(null); refresh() }, onError: (e: any) => toast.error(e.message),
  })
  const isAdmin = hasRole(role, 'admin')

  return (
    <div className="mx-auto max-w-6xl p-6">
      <PageHeader title="Integration Hub" subtitle="Connect CRM, email, databases and document storage. Credentials are encrypted server-side and never returned."
        actions={isAdmin && <Button onClick={() => setOpen(true)}><Plug className="h-4 w-4" />Connect</Button>} />
      <div className="mb-4 rounded-lg border border-cyan/30 bg-cyan/10 p-3 text-xs text-cyan">Email delivery currently uses a built-in mock provider, so no real emails leave the system. Real provider adapters plug in here.</div>
      {list.isLoading ? <Skeleton className="h-40" /> : !list.data?.length ? (
        <Card><EmptyState icon={<Plug className="h-6 w-6" />} title="No integrations connected" hint="The system works with internal mock data until you connect real sources." /></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {list.data.map((i) => { const Icon = ICON[i.kind] ?? Plug; return (
            <Card key={i.id} className="space-y-3 p-4">
              <div className="flex items-start justify-between"><div className="grid h-9 w-9 place-items-center rounded-lg bg-violet/15 text-violet"><Icon className="h-4 w-4" /></div><StatusBadge status={i.status} /></div>
              <div><div className="font-medium">{i.name}</div><div className="text-xs text-muted">{i.kind} · {i.provider}</div></div>
              <div className="text-[11px] text-muted">Last health check: {timeAgo(i.last_health_at)} · Rotated: {timeAgo(i.last_rotated_at)}</div>
              <div className="flex gap-2">
                {hasRole(role, 'operator') && <Button size="sm" variant="outline" onClick={() => health.mutate(i.id)}>Test</Button>}
                {isAdmin && <Button size="sm" variant="outline" onClick={() => { setRotate(i); setCfg('{}') }}>Rotate</Button>}
                {isAdmin && <Button size="sm" variant="danger" onClick={() => window.confirm('Remove this integration?') && del.mutate(i.id)}>Remove</Button>}
              </div>
            </Card>) })}
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Connect an integration">
        <form id="int-form" className="space-y-3" onSubmit={handleSubmit(async (v: any) => {
          try { await api.post('/integrations', { ...v, config: JSON.parse(v.config || '{}') }); toast.success('Connected'); setOpen(false); reset(); refresh() }
          catch (e: any) { toast.error(e.message) }
        })}>
          <Field label="Type"><Select {...register('kind')}>{['crm', 'email', 'database', 'storage'].map((k) => <option key={k}>{k}</option>)}</Select></Field>
          <Field label="Name" error={errors.name?.message as string}><Input {...register('name')} /></Field>
          <Field label="Provider" error={errors.provider?.message as string}><Input {...register('provider')} /></Field>
          <Field label="Credentials (JSON, encrypted at rest)" error={errors.config?.message as string}><Textarea rows={4} className="font-mono text-xs" {...register('config')} /></Field>
          <Button className="w-full" loading={isSubmitting}>Connect</Button>
        </form>
      </Modal>
      <Modal open={!!rotate} onClose={() => setRotate(null)} title={`Rotate credentials · ${rotate?.name ?? ''}`}
        footer={<><Button variant="ghost" onClick={() => setRotate(null)}>Cancel</Button><Button loading={doRotate.isPending} onClick={() => doRotate.mutate()}>Rotate</Button></>}>
        <Field label="New credentials (JSON)"><Textarea rows={5} className="font-mono text-xs" value={cfg} onChange={(e) => setCfg(e.target.value)} /></Field>
      </Modal>
    </div>
  )
}
