import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, Database, Rocket, Users } from 'lucide-react'
import { toast } from 'sonner'
import { Badge, Button, Card, Field, Input, Select } from '@/components/ui'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useAuth } from '@/stores/auth'

const STEPS = [{ icon: Users, label: 'Team' }, { icon: Database, label: 'Data' }, { icon: Rocket, label: 'First mission' }]
const FIRST_PROMPT = 'Find all overdue invoices, prepare personalized follow-up emails and generate a collection report.'

export function Onboarding() {
  const org = useAuth((s) => s.org)
  const nav = useNavigate()
  const [step, setStep] = useState(0)
  const [inv, setInv] = useState({ email: '', full_name: '', role: 'operator' })
  const [temp, setTemp] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)

  const invite = async () => {
    setBusy(true)
    try { const r: any = await api.post('/auth/invite', inv); setTemp(r.temporary_password); toast.success('Teammate added') }
    catch (e: any) { toast.error(e.message) } finally { setBusy(false) }
  }
  const loadDemo = async () => {
    setBusy(true)
    try { await api.post('/admin/demo-data'); setLoaded(true); toast.success('Demo customers, invoices and policy documents loaded') }
    catch (e: any) { toast.error(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="grid min-h-full place-items-center p-4">
      <div className="w-full max-w-xl">
        <div className="mb-6 text-center"><h1 className="text-xl font-semibold">Set up {org?.name}</h1><p className="text-sm text-muted">Three quick steps. Everything is skippable.</p></div>
        <div className="mb-5 flex items-center justify-center gap-2">
          {STEPS.map((s, i) => (
            <div key={s.label} className="flex items-center gap-2">
              <div className={cn('flex items-center gap-2 rounded-full border px-3 py-1 text-xs', i === step ? 'border-violet bg-violet/15 text-violet' : i < step ? 'border-ok/40 text-ok' : 'text-muted')}>
                {i < step ? <Check className="h-3 w-3" /> : <s.icon className="h-3 w-3" />}{s.label}
              </div>
              {i < 2 && <div className="h-px w-6 bg-border" />}
            </div>
          ))}
        </div>
        <Card className="space-y-4 p-6">
          {step === 0 && (<>
            <h2 className="font-semibold">Invite a teammate</h2>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Name"><Input value={inv.full_name} onChange={(e) => setInv({ ...inv, full_name: e.target.value })} /></Field>
              <Field label="Email"><Input type="email" value={inv.email} onChange={(e) => setInv({ ...inv, email: e.target.value })} /></Field>
            </div>
            <Field label="Role"><Select value={inv.role} onChange={(e) => setInv({ ...inv, role: e.target.value })}>
              {['viewer', 'operator', 'admin'].map((r) => <option key={r}>{r}</option>)}</Select></Field>
            {temp && <div className="rounded-lg bg-panel2 p-3 text-xs">Temporary password (share securely): <code className="text-cyan">{temp}</code></div>}
            <div className="flex justify-between">
              <Button variant="outline" loading={busy} disabled={!inv.email || !inv.full_name} onClick={invite}>Send invite</Button>
              <Button onClick={() => setStep(1)}>Continue</Button>
            </div>
          </>)}
          {step === 1 && (<>
            <h2 className="font-semibold">Business data and knowledge</h2>
            <p className="text-sm text-muted">New organizations start empty. Load synthetic customers, overdue invoices and policy documents so the agents have something to work on. You can upload your own documents later in the Knowledge Vault.</p>
            {loaded && <Badge tone="ok">Demo data loaded</Badge>}
            <div className="flex justify-between">
              <Button variant="outline" loading={busy} disabled={loaded} onClick={loadDemo}>Load demo data</Button>
              <Button onClick={() => setStep(2)}>Continue</Button>
            </div>
          </>)}
          {step === 2 && (<>
            <h2 className="font-semibold">Run your first mission</h2>
            <p className="rounded-lg bg-panel2 p-3 text-sm">{FIRST_PROMPT}</p>
            <div className="flex justify-between">
              <Button variant="ghost" onClick={() => nav('/')}>Skip</Button>
              <Button onClick={() => nav('/', { state: { prompt: FIRST_PROMPT } })}>Open Command Center</Button>
            </div>
          </>)}
        </Card>
      </div>
    </div>
  )
}
