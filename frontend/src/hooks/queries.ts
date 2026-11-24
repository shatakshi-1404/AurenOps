import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Dashboard } from '@/types'

export const useDashboard = () =>
  useQuery({ queryKey: ['dashboard'], queryFn: () => api.get<Dashboard>('/dashboard'), refetchInterval: 10000 })
