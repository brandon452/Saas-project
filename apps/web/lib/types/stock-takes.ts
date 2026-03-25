export type StockTakeStatus =
  | "DRAFT"
  | "IN_PROGRESS"
  | "PENDING_APPROVAL"
  | "COMPLETED"
  | "CANCELLED"

export interface StockTakeLine {
  id: number
  org_item: string
  item_name: string
  item_sku: string
  snapshot_quantity: string
  counted_quantity: string | null
  variance_preview: string | null
}

export interface StockTake {
  id: string
  branch: string | { id: string; name?: string; code?: string }
  status: StockTakeStatus
  notes: string
  created_by: string | null
  started_by: string | null
  submitted_by: string | null
  approved_by: string | null
  cancelled_by: string | null
  started_at: string | null
  submitted_at: string | null
  approved_at: string | null
  cancelled_at: string | null
  created_at: string
  updated_at: string
}

export interface StockTakeDetail extends StockTake {
  lines: StockTakeLine[]
}

export interface CreateStockTakePayload {
  branch: string
  notes?: string
}

export interface UpdateStockTakeNotesPayload {
  notes: string
}

export interface UpdateStockTakeLinePayload {
  counted_quantity: string | null
}
