import { createBrowserRouter, Navigate, Outlet, useLocation } from 'react-router-dom'
import { useEffect, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import { EmptyState } from '@/components/ui'
import { api } from '@/lib/api'
import { hasRole } from '@/lib/utils'
import { useAuth } from '@/stores/auth'
import type { Me } from '@/types'
import { ForgotPassword, Login, Register, ResetPassword } from '@/features/auth/AuthPages'
import { Onboarding } from '@/features/auth/Onboarding'
import { CommandCenter } from '@/features/dashboard/CommandCenter'
import { ApprovalInbox } from '@/features/approvals/ApprovalInbox'
import { Observatory } from '@/features/observatory/Observatory'
import { KnowledgeVault } from '@/features/knowledge-vault/KnowledgeVault'
import { Integrations } from '@/features/integrations/Integrations'
import { Admin } from '@/features/admin/Admin'

function Protected() {
  const token = useAuth((s) => s.token)
  const setMe = useAuth((s) => s.setMe)
  const loc = useLocation()
  const { data } = useQuery({ queryKey: ['me', token], queryFn: () => api.get<Me>('/auth/me'), enabled: !!token })
  useEffect(() => { if (data) setMe(data) }, [data, setMe])
  if (!token) return <Navigate to="/login" replace state={{ from: loc.pathname }} />
  return <Outlet />
}

function RoleGate({ min, children }: { min: 'operator' | 'admin' | 'owner'; children: ReactNode }) {
  const role = useAuth((s) => s.role)
  if (!hasRole(role, min)) return <EmptyState title="Access restricted" hint={`This area requires the ${min} role.`} />
  return <>{children}</>
}

export const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  { path: '/register', element: <Register /> },
  { path: '/forgot-password', element: <ForgotPassword /> },
  { path: '/reset-password', element: <ResetPassword /> },
  {
    element: <Protected />,
    children: [
      { path: '/onboarding', element: <Onboarding /> },
      {
        element: <AppShell />,
        children: [
          { path: '/', element: <CommandCenter /> },
          { path: '/operations', lazy: async () => ({ Component: (await import('@/features/mission-canvas/OperationsPage')).OperationsPage }) },
          { path: '/operations/:id', lazy: async () => ({ Component: (await import('@/features/mission-canvas/OperationsPage')).OperationsPage }) },
          { path: '/approvals', element: <ApprovalInbox /> },
          { path: '/approvals/:id', element: <ApprovalInbox /> },
          { path: '/observatory', element: <Observatory /> },
          { path: '/knowledge', element: <KnowledgeVault /> },
          { path: '/integrations', element: <Integrations /> },
          { path: '/analytics', lazy: async () => ({ Component: (await import('@/features/analytics/Analytics')).Analytics }) },
          { path: '/admin', element: <RoleGate min="admin"><Admin /></RoleGate> },
        ],
      },
    ],
  },
])
