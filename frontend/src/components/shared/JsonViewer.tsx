import { lazy, Suspense } from 'react'
import { Skeleton } from '@/components/ui'
import { useUI } from '@/stores/ui'

const Editor = lazy(() => import('@monaco-editor/react'))

export function JsonViewer({ value, height = 260 }: { value: unknown; height?: number }) {
  const theme = useUI((s) => s.theme)
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <Suspense fallback={<Skeleton className="h-40" />}>
        <Editor height={height} language="json" theme={theme === 'dark' ? 'vs-dark' : 'light'}
          value={typeof value === 'string' ? value : JSON.stringify(value ?? null, null, 2)}
          options={{ readOnly: true, minimap: { enabled: false }, fontSize: 12, scrollBeyondLastLine: false, wordWrap: 'on', lineNumbers: 'off', folding: true }} />
      </Suspense>
    </div>
  )
}
