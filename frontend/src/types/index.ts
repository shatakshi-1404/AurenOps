export type Role = 'viewer' | 'operator' | 'admin' | 'owner'
export interface UserRef { id: string; email: string; full_name: string }
export interface OrgRef { id: string; name: string; role?: Role }
export interface TokenResponse { access_token: string; user: UserRef; org: { id: string; name: string }; role: Role }
export interface Me { user: UserRef; org_id: string; role: Role; organizations: { id: string; name: string; role: Role }[] }

export type RunStatus = 'QUEUED' | 'PLANNING' | 'RUNNING' | 'WAITING_FOR_APPROVAL' | 'APPROVED' | 'EXECUTING'
  | 'VERIFYING' | 'COMPLETED' | 'FAILED' | 'RETRYING' | 'REJECTED' | 'CANCELLED'
export interface PlanStep { key: string; agent: string; description: string }
export interface Plan { intent: string; params: Record<string, any>; source: string; steps: PlanStep[] }
export interface Run {
  id: string; request: string; intent: string | null; status: RunStatus; plan: Plan | null
  result: any; error: string | null; token_usage: number
  created_at: string; started_at: string | null; finished_at: string | null
}
export interface NodeRec {
  id: string; node_key: string; agent_key: string; status: string; attempts: number
  input: any; output: any; error: string | null; started_at: string | null; finished_at: string | null; duration_ms: number | null
}
export interface RunDetail extends Run { nodes: NodeRec[]; approvals: ApprovalSummary[] }
export interface GraphNode { id: string; label: string; agent: string; status: string; duration_ms: number | null; attempts: number }
export interface Graph { run_id: string; status: RunStatus; nodes: GraphNode[]; edges: { id: string; source: string; target: string; animated: boolean }[] }
export interface RunEvent { id: string; event: string; run_id: string; node_id: string | null; status: string | null; timestamp: string; data: any }

export interface ApprovalSummary {
  id: string; run_id: string; action: string; title: string; reason: string; agent_key: string; policy: string
  risk: string; status: string; payload: { email_ids: string[]; items: EvidenceItem[]; total_outstanding: number }
  payload_hash: string; created_at: string; expires_at: string | null; decided_at: string | null; decision_note: string | null
}
export interface EvidenceItem {
  email_id: string; to: string; subject: string; invoice_number: string; invoice_id: string; customer: string
  outstanding: number; days_overdue: number; tier: string; reminders_sent: number
}
export interface Draft {
  id: string; to_email: string; subject: string; body: string; original_subject: string; original_body: string
  edited: boolean; status: string; invoice_id: string; customer_id: string; error: string | null
}
export interface ApprovalDetail extends ApprovalSummary { current_payload_hash: string; drafts: Draft[] }

export interface Dashboard {
  active_agents: number; runs_in_flight: number; pending_approvals: number; tasks_completed_30d: number
  success_rate: number | null; approval_turnaround_seconds: number | null; avg_execution_seconds: number | null
  emails_sent_30d: number; estimated_minutes_saved: number
  agent_performance: { agent: string; executions: number; avg_ms: number; failures: number }[]
  runs_per_day: { day: string; runs: number }[]; recent_runs: Run[]
}
export interface Agent { id: string; key: string; name: string; description: string; enabled: boolean }
export interface Notif { id: string; title: string; body: string; link: string | null; read: boolean; created_at: string }
export interface DocumentRec {
  id: string; filename: string; category: string; status: string; error: string | null
  access_roles: string[] | null; chunk_count: number; created_at: string
}
export interface SearchResult {
  chunk_id: string; document_id: string; filename: string; chunk_index: number; content: string
  similarity: number; fts_rank: number; score: number; citation: string
}
export interface IntegrationRec {
  id: string; kind: string; name: string; provider: string; status: string
  last_health_at: string | null; last_rotated_at: string | null; created_at: string
}
export interface ReportRec { id: string; kind: string; summary: any; created_at: string; run_id: string | null }
export interface Policy { mode: 'auto' | 'approval' | 'restricted'; risk?: string; approver_min_role?: Role }
