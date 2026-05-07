export type StockTakeStatus =
  | "DRAFT"
  | "IN_PROGRESS"
  | "PENDING_APPROVAL"
  | "COMPLETED"
  | "COMPLETED_WITH_VARIANCES"
  | "CANCELLED"

export type StockTakeType = "FULL" | "CYCLE"
export type CycleItemClass = "A" | "B" | "C"

export interface StockTakeLine {
  id: number
  org_item: string
  item_name: string
  item_sku: string
  snapshot_quantity: string
  counted_quantity: string | null
  variance_preview: string | null
}

export interface StockTakeUser {
  id: number
  username: string
}

export interface StockTake {
  id: string
  branch: string | { id: string; name?: string; code?: string }
  status: StockTakeStatus
  stock_take_type: StockTakeType
  cycle_item_class: CycleItemClass | null
  scheduled_for: string | null
  notes: string
  total_lines_count: number
  counted_lines_count: number
  created_by: StockTakeUser | null
  started_by: StockTakeUser | null
  submitted_by: StockTakeUser | null
  approved_by: StockTakeUser | null
  cancelled_by: StockTakeUser | null
  reopened_by: StockTakeUser | null
  started_at: string | null
  submitted_at: string | null
  approved_at: string | null
  cancelled_at: string | null
  reopened_at: string | null
  snapshot_taken_at: string | null
  created_at: string
  updated_at: string
}

export interface StockTakeDetail extends StockTake {
  lines: StockTakeLine[]
}

export interface CreateStockTakePayload {
  branch: string
  notes?: string
  stock_take_type?: StockTakeType
  cycle_item_class?: CycleItemClass
  scheduled_for?: string
}

export interface GenerateCycleCountPayload {
  branch_id: string
  cycle_item_class: CycleItemClass
  scheduled_for?: string
}

export interface UpdateStockTakeNotesPayload {
  notes: string
}

export interface UpdateStockTakeLinePayload {
  counted_quantity: string | null
}

export interface BulkUpdateStockTakeLinesPayload {
  lines: Array<{
    id: number
    counted_quantity: string | null
  }>
}
