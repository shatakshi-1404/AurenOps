import { useEffect, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { ApiError } from '@/lib/api'
import { useUI } from '@/stores/ui'

const client = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000, refetchOnWindowFocus: false,
      retry: (n, e) => !(e instanceof ApiError && e.status < 500) && n < 2,
    },
  },
})

export function Providers({ children }: { children: ReactNode }) {
  const theme = useUI((s) => s.theme)
  useEffect(() => { document.documentElement.classList.toggle('dark', theme === 'dark') }, [theme])
  return (
    <QueryClientProvider client={client}>
      {children}
      <Toaster theme={theme} position="bottom-right" richColors />
    </QueryClientProvider>
  )
}
