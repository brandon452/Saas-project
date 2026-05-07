export type ScanOutcome =
  | "matched"
  | "not_found"
  | "not_enabled_at_branch"
  | "not_in_count"
  | "ambiguous"

export interface ScanResolvedItem {
  org_item_id: string
  master_item_id: string
  name: string
  sku: string
  is_lot_tracked: boolean
  is_expiry_tracked: boolean
  branch_item_id: number
  stock_take_line_id?: number
  snapshot_quantity?: string
  counted_quantity?: string | null
}

export interface ScanResolveResult {
  outcome: ScanOutcome
  item: ScanResolvedItem | null
}

export type ScanStatus =
  | "idle"
  | "captured"
  | "resolved"
  | "pending_submit"
  | "retrying"
  | "failed"
  | "synced"

export interface RetryQueueEntry {
  id: string
  idempotencyKey: string
  workflow: "receive" | "pick" | "count" | "transfer_receive" | "transfer_dispatch"
  payload: unknown
  endpoint: string
  method: string
  attemptCount: number
  lastAttemptAt: number | null
  createdAt: number
  nonRetryable: boolean
  error: string | null
}
