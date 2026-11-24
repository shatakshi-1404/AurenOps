import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, RefreshCw, Search, Trash2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Badge, Button, Card, EmptyState, Input, Modal, Select, Skeleton } from '@/components/ui'
import { api } from '@/lib/api'
import { hasRole, timeAgo } from '@/lib/utils'
import { useAuth } from '@/stores/auth'
import type { DocumentRec, SearchResult } from '@/types'

const ROLES = ['viewer', 'operator', 'admin', 'owner']

export function KnowledgeVault() {
  const qc = useQueryClient()
  const role = useAuth((s) => s.role)
  const fileRef = useRef<HTMLInputElement>(null)
  const [category, setCategory] = useState('general')
  const [access, setAccess] = useState<string[]>([])
  const [chunksFor, setChunksFor] = useState<DocumentRec | null>(null)
  const [query, setQuery] = useState('')
  const [k, setK] = useState(5)

  const docs = useQuery({
    queryKey: ['documents'], queryFn: () => api.get<DocumentRec[]>('/documents'),
    refetchInterval: (q) => (q.state.data?.some((d) => d.status === 'processing') ? 3000 : false),
  })
  const chunks = useQuery({ queryKey: ['chunks', chunksFor?.id], enabled: !!chunksFor, queryFn: () => api.get<any[]>(`/documents/${chunksFor!.id}/chunks`) })
  const refresh = () => qc.invalidateQueries({ queryKey: ['documents'] })

  const upload = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData()
      fd.append('file', file); fd.append('category', category); fd.append('access_roles', access.join(','))
      return api.upload('/documents', fd)
    },
    onSuccess: () => { toast.success('Uploaded. Indexing in the background.'); refresh() },
    onError: (e: any) => toast.error(e.message),
  })
  const reindex = useMutation({ mutationFn: (id: string) => api.post(`/documents/${id}/reindex`), onSuccess: () => { toast.success('Re-indexing'); refresh() }, onError: (e: any) => toast.error(e.message) })
  const del = useMutation({ mutationFn: (id: string) => api.del(`/documents/${id}`), onSuccess: () => { toast.success('Deleted'); refresh() }, onError: (e: any) => toast.error(e.message) })
  const search = useMutation({ mutationFn: () => api.post<{ results: SearchResult[] }>('/knowledge/search', { query, k }), onError: (e: any) => toast.error(e.message) })

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <PageHeader title="Knowledge Vault" subtitle="Company documents that agents retrieve evidence from. Access is enforced per organization and role." />

      {hasRole(role, 'operator') && (
        <Card className="space-y-3 p-4">
          <div className="text-sm font-semibold">Upload a document</div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Select value={category} onChange={(e) => setCategory(e.target.value)}>
              {['general', 'communication', 'policy', 'sop', 'vendor'].map((c) => <option key={c}>{c}</option>)}</Select>
            <div className="flex flex-wrap items-center gap-3 text-xs sm:col-span-2">
              <span className="text-muted">Visible to (none = everyone):</span>
              {ROLES.map((r) => <label key={r} className="flex items-center gap-1"><input type="checkbox" className="accent-violet" checked={access.includes(r)}
                onChange={() => setAccess((a) => (a.includes(r) ? a.filter((x) => x !== r) : [...a, r]))} />{r}</label>)}
            </div>
          </div>
          <input ref={fileRef} type="file" hidden accept=".pdf,.docx,.txt,.md" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = '' }} />
          <Button variant="outline" loading={upload.isPending} onClick={() => fileRef.current?.click()}><Upload className="h-4 w-4" />Choose PDF, DOCX, TXT or MD</Button>
        </Card>
      )}

      <Card>
        {docs.isLoading ? <Skeleton className="h-40" /> : !docs.data?.length ? (
          <EmptyState icon={<FileText className="h-6 w-6" />} title="No documents yet" hint="Upload invoice policies, communication guidelines or SOPs." />
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-xs text-muted"><th className="p-3">Document</th><th>Category</th><th>Status</th><th>Chunks</th><th>Access</th><th>Added</th><th /></tr></thead>
            <tbody>{docs.data.map((d) => (
              <tr key={d.id} className="border-b border-border/60">
                <td className="p-3"><button className="text-left font-medium hover:text-violet" onClick={() => setChunksFor(d)}>{d.filename}</button>{d.error && <div className="text-xs text-bad">{d.error}</div>}</td>
                <td><Badge>{d.category}</Badge></td><td><StatusBadge status={d.status} /></td><td>{d.chunk_count}</td>
                <td className="text-xs text-muted">{d.access_roles?.join(', ') ?? 'everyone'}</td><td className="text-xs text-muted">{timeAgo(d.created_at)}</td>
                <td className="pr-3 text-right">
                  {hasRole(role, 'operator') && <Button size="sm" variant="ghost" onClick={() => reindex.mutate(d.id)}><RefreshCw className="h-3.5 w-3.5" /></Button>}
                  {hasRole(role, 'admin') && <Button size="sm" variant="ghost" onClick={() => window.confirm(`Delete ${d.filename}?`) && del.mutate(d.id)}><Trash2 className="h-3.5 w-3.5 text-bad" /></Button>}
                </td>
              </tr>))}</tbody>
          </table>
        )}
      </Card>

      <Card className="space-y-4 p-4">
        <div className="text-sm font-semibold">Search testing</div>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (query.trim().length > 1) search.mutate() }}>
          <Input placeholder="e.g. what tone for 60 days overdue?" value={query} onChange={(e) => setQuery(e.target.value)} />
          <Select className="w-24" value={k} onChange={(e) => setK(Number(e.target.value))}>{[3, 5, 10].map((n) => <option key={n} value={n}>top {n}</option>)}</Select>
          <Button loading={search.isPending}><Search className="h-4 w-4" />Search</Button>
        </form>
        {search.data && (search.data.results.length === 0 ? <div className="text-sm text-muted">No evidence passed the relevance filter.</div> : (
          <div className="space-y-3">{search.data.results.map((r) => (
            <div key={r.chunk_id} className="rounded-lg border border-border bg-panel2 p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2 text-xs"><Badge tone="violet">{r.citation}</Badge>
                <span className="text-muted">similarity {r.similarity}</span><span className="text-muted">fts {r.fts_rank}</span><span className="text-muted">rrf {r.score}</span></div>
              <p className="whitespace-pre-wrap text-sm">{r.content}</p></div>
          ))}</div>
        ))}
      </Card>

      <Modal open={!!chunksFor} onClose={() => setChunksFor(null)} title={`Chunks · ${chunksFor?.filename ?? ''}`} wide>
        {chunks.isLoading ? <Skeleton className="h-40" /> : <div className="space-y-2">{chunks.data?.map((c) => (
          <div key={c.id} className="rounded-lg bg-panel2 p-3"><div className="mb-1 text-[10px] text-muted">chunk {c.idx}</div><p className="whitespace-pre-wrap text-xs">{c.content}</p></div>))}</div>}
      </Modal>
    </div>
  )
}
