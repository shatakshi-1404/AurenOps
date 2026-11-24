import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UIState { theme: 'dark' | 'light'; navOpen: boolean; toggleTheme: () => void; setNav: (b: boolean) => void }

export const useUI = create<UIState>()(
  persist(
    (set) => ({
      theme: 'dark', navOpen: false,
      toggleTheme: () => set((s) => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),
      setNav: (navOpen) => set({ navOpen }),
    }),
    { name: 'aurenops-ui', partialize: (s) => ({ theme: s.theme }) },
  ),
)
