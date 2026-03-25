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
  results: StockValuationRow[]
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
