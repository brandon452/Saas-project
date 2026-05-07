export interface StockValuationSummary {
  total_latest_valuation: string | null
  total_average_valuation: string | null
  item_count: number
  branch_count: number
}

export interface StockValuationRow {
  item_id: string
  item_name: string
  item_sku: string
  branch_id: string
  branch_name: string
  quantity_on_hand: string
  latest_unit_cost: string | null
  latest_valuation: string | null
  average_unit_cost: string | null
  average_valuation: string | null
}

export interface StockValuationResponse {
  summary: StockValuationSummary
  count: number
  next: string | null
  previous: string | null
  results: StockValuationRow[]
}

export interface InventoryAgingSummary {
  total_latest_valuation: string | null
  total_average_valuation: string | null
  item_count: number
  branch_count: number
  oldest_age_days: number | null
}

export interface InventoryAgingRow {
  item_id: string
  item_name: string
  item_sku: string
  branch_id: string
  branch_name: string
  quantity_on_hand: string
  last_receipt_at: string | null
  age_days: number | null
  latest_unit_cost: string | null
  latest_valuation: string | null
  average_unit_cost: string | null
  average_valuation: string | null
}

export interface InventoryAgingResponse {
  summary: InventoryAgingSummary
  count: number
  next: string | null
  previous: string | null
  results: InventoryAgingRow[]
}

export interface SlowDeadStockSummary {
  slow_count: number
  dead_count: number
  total_slow_valuation: string | null
  total_dead_valuation: string | null
}

export interface SlowDeadStockRow {
  item_id: string
  item_name: string
  item_sku: string
  branch_id: string
  branch_name: string
  quantity_on_hand: string
  last_outbound_at: string | null
  inactive_days: number
  status: "SLOW" | "DEAD"
  latest_unit_cost: string | null
  latest_valuation: string | null
}

export interface SlowDeadStockResponse {
  summary: SlowDeadStockSummary
  count: number
  next: string | null
  previous: string | null
  results: SlowDeadStockRow[]
}

export interface CostTrendPoint {
  date: string
  unit_cost: string
  quantity_received: number
  supplier_id: string | null
  supplier_name: string | null
  branch_id: string
  branch_name: string
  receipt_id: string
  receipt_type: "PO_RECEIPT" | "DIRECT_RECEIPT"
}

export interface CostTrendResponse {
  results: CostTrendPoint[]
  truncated: boolean
  total_count: number
  limit: number
}
