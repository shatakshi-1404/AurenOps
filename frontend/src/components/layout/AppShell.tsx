import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Activity, BarChart3, Bell, BookOpen, Building2, Check, ChevronsUpDown, Home, Inbox, LogOut, Menu, Moon, Plug, Plus, Shield, Sun, Workflow,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge, Popover } from '@/components/ui'
import { useDashboard } from '@/hooks/queries'
import { api } from '@/lib/api'
import { cn, hasRole, timeAgo } from '@/lib/utils'
import { useAuth } from '@/stores/auth'
import { useUI } from '@/stores/ui'
import type { Notif, TokenResponse } from '@/types'

const NAV = [
  { to: '/', label: 'Command Center', icon: Home, min: 'viewer' },
  { to: '/operations', label: 'Mission Canvas', icon: Workflow, min: 'viewer' },
  { to: '/approvals', label: 'Approval Inbox', icon: Inbox, min: 'viewer', badge: true },
  { to: '/observatory', label: 'Agent Observatory', icon: Activity, min: 'viewer' },
  { to: '/knowledge', label: 'Knowledge Vault', icon: BookOpen, min: 'viewer' },
  { to: '/integrations', label: 'Integration Hub', icon: Plug, min: 'viewer' },
  { to: '/analytics', label: 'Analytics', icon: BarChart3, min: 'viewer' },
  { to: '/admin', label: 'Admin & Governance', icon: Shield, min: 'admin' },
] as const

function Sidebar() {
  const role = useAuth((s) => s.role)
  const setNav = useUI((s) => s.setNav)
  const { data } = useDashboard()
  return (
    <nav className="flex h-full w-64 flex-col border-r border-border bg-panel">
      <Link to="/" className="flex items-center gap-2.5 px-5 py-5" onClick={() => setNav(false)}>
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-violet to-cyan text-sm font-bold text-white">A</div>
        <div>
          <div className="text-sm font-bold tracking-[0.18em]">AURENOPS</div>
          <div className="flex items-center gap-1.5 text-[10px] text-muted"><span className="h-1.5 w-1.5 rounded-full bg-ok" />All systems operational</div>
        </div>
      </Link>
      <div className="flex-1 space-y-1 px-3">
        {NAV.filter((n) => hasRole(role, n.min)).map((n) => (
          <NavLink key={n.to} to={n.to} end={n.to === '/'} onClick={() => setNav(false)}
            className={({ isActive }) => cn('flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition',
              isActive ? 'bg-violet/15 text-violet' : 'text-muted hover:bg-panel2 hover:text-fg')}>
            <n.icon className="h-4 w-4" />
            <span className="flex-1">{n.label}</span>
            {'badge' in n && !!data?.pending_approvals && <Badge tone="warn">{data.pending_approvals}</Badge>}
          </NavLink>
        ))}
      </div>
      <div className="px-5 py-4 text-[10px] text-muted">Role: <span className="font-medium text-fg">{role}</span></div>
    </nav>
  )
}

function OrgSwitcher() {
  const { org, orgs, setSession } = useAuth()
  const qc = useQueryClient()
  const nav = useNavigate()
  const switchOrg = async (id: string) => {
    try {
      setSession(await api.post<TokenResponse>('/auth/switch-org', { org_id: id }))
      qc.clear(); nav('/')
    } catch (e: any) { toast.error(e.message) }
  }
  const create = async () => {
    const name = window.prompt('New organization name')
    if (!name) return
    try {
      setSession(await api.post<TokenResponse>('/auth/orgs', { name }))
      qc.clear(); nav('/onboarding')
    } catch (e: any) { toast.error(e.message) }
  }
  return (
    <Popover align="left" button={(_, t) => (
      <button onClick={t} className="flex items-center gap-2 rounded-lg border border-border bg-panel2 px-3 py-1.5 text-sm">
        <Building2 className="h-4 w-4 text-muted" /><span className="max-w-[160px] truncate">{org?.name}</span><ChevronsUpDown className="h-3.5 w-3.5 text-muted" />
      </button>)}>
      {(close) => (
        <div>
          {orgs.map((o) => (
            <button key={o.id} onClick={() => { close(); if (o.id !== org?.id) switchOrg(o.id) }}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-panel2">
              <span className="truncate">{o.name}</span>{o.id === org?.id && <Check className="h-4 w-4 text-violet" />}
            </button>
          ))}
          <button onClick={() => { close(); create() }} className="mt-1 flex w-full items-center gap-2 rounded-lg border-t border-border px-3 py-2 text-sm text-violet hover:bg-panel2">
            <Plus className="h-4 w-4" />New organization
          </button>
        </div>
      )}
    </Popover>
  )
}

function Notifications() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const { data = [] } = useQuery({ queryKey: ['notifications'], queryFn: () => api.get<Notif[]>('/admin/notifications'), refetchInterval: 15000 })
  const read = useMutation({
    mutationFn: (id: string) => api.post(`/admin/notifications/${id}/read`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })
  const unread = data.filter((n) => !n.read).length
  return (
    <Popover button={(_, t) => (
      <button onClick={t} className="relative rounded-lg p-2 text-muted hover:bg-panel2 hover:text-fg">
        <Bell className="h-4 w-4" />
        {unread > 0 && <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-violet" />}
      </button>)}>
      {(close) => (
        <div className="max-h-96 w-80 overflow-y-auto">
          <div className="px-3 py-2 text-xs font-semibold text-muted">Notifications</div>
          {data.length === 0 && <div className="px-3 py-6 text-center text-xs text-muted">Nothing yet</div>}
          {data.map((n) => (
            <button key={n.id} onClick={() => { close(); if (!n.read) read.mutate(n.id); if (n.link) nav(n.link) }}
              className="flex w-full items-start gap-2 rounded-lg px-3 py-2 text-left hover:bg-panel2">
              <span className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-full', n.read ? 'bg-transparent' : 'bg-violet')} />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{n.title}</span>
                <span className="block truncate text-xs text-muted">{n.body}</span>
                <span className="text-[10px] text-muted">{timeAgo(n.created_at)}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </Popover>
  )
}

function Topbar() {
  const { user, logout } = useAuth()
  const { theme, toggleTheme, setNav } = useUI()
  const qc = useQueryClient()
  const nav = useNavigate()
  const signOut = async () => {
    try { await api.post('/auth/logout') } catch { /* token may already be invalid */ }
    logout(); qc.clear(); nav('/login')
  }
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-panel/80 px-4 backdrop-blur">
      <div className="flex items-center gap-3">
        <button className="rounded-lg p-2 text-muted hover:bg-panel2 lg:hidden" onClick={() => setNav(true)}><Menu className="h-4 w-4" /></button>
        <OrgSwitcher />
      </div>
      <div className="flex items-center gap-1">
        <button onClick={toggleTheme} className="rounded-lg p-2 text-muted hover:bg-panel2 hover:text-fg">
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
        <Notifications />
        <Popover button={(_, t) => (
          <button onClick={t} className="ml-1 grid h-8 w-8 place-items-center rounded-full bg-violet/20 text-xs font-semibold text-violet">
            {user?.full_name?.[0]?.toUpperCase() ?? 'U'}
          </button>)}>
          {() => (
            <div>
              <div className="px-3 py-2"><div className="text-sm font-medium">{user?.full_name}</div><div className="text-xs text-muted">{user?.email}</div></div>
              <button onClick={signOut} className="flex w-full items-center gap-2 rounded-lg border-t border-border px-3 py-2 text-sm text-bad hover:bg-panel2"><LogOut className="h-4 w-4" />Sign out</button>
            </div>
          )}
        </Popover>
      </div>
    </header>
  )
}

export function AppShell() {
  const { navOpen, setNav } = useUI()
  return (
    <div className="flex h-full">
      <div className="hidden lg:block"><Sidebar /></div>
      {navOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <Sidebar /><div className="flex-1 bg-black/60" onClick={() => setNav(false)} />
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="min-h-0 flex-1 overflow-y-auto"><Outlet /></main>
      </div>
    </div>
  )
}
