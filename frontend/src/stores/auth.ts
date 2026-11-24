import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Me, OrgRef, Role, TokenResponse, UserRef } from '@/types'

interface AuthState {
  token: string | null; user: UserRef | null; org: { id: string; name: string } | null
  role: Role | null; orgs: OrgRef[]
  setSession: (r: TokenResponse) => void
  setMe: (m: Me) => void
  logout: () => void
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      token: null, user: null, org: null, role: null, orgs: [],
      setSession: (r) => set({ token: r.access_token, user: r.user, org: r.org, role: r.role }),
      setMe: (m) => set((s) => ({
        user: m.user, role: m.role, orgs: m.organizations,
        org: m.organizations.find((o) => o.id === m.org_id) ?? s.org,
      })),
      logout: () => set({ token: null, user: null, org: null, role: null, orgs: [] }),
    }),
    { name: 'aurenops-auth' },
  ),
)
