export interface AuditActor {
  id: string | null
  type: "user" | "system"
  email: string
  name: string
}

export interface AuditEvent {
  id: string
  occurred_at: string
  event_type: string
  resource_type: string
  resource_id: string
  summary: string
  metadata_json: Record<string, unknown>
  diff_json: Record<string, unknown> | null
  actor: AuditActor
}

export interface AuditEventListResponse {
  count: number
  next: string | null
  previous: string | null
  results: AuditEvent[]
}
