export interface AdjustmentItemResult {
  id: string
  name: string
  sku: string
}

export interface PostAdjustmentPayload {
  item: string
  quantity: string
  movement_type: "ADJUSTMENT"
  reason?: string
  idempotency_key: string
}

export interface StockLedgerEntry {
  id: string
  organization: string
  branch: { id: string; name: string; code: string }
  item: { id: string; name: string; sku: string }
  quantity: string
  movement_type: string
  reference_type: string | null
  reference_id: string | null
  reason: string | null
  performed_by: { id: string; username: string } | null
  occurred_at: string
  created_at: string
}

export interface StockMovementsResponse {
  results: StockLedgerEntry[]
  next: string | null
  previous: string | null
  count: number
}
