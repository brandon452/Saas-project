export type QuickSaleStatus = "CONFIRMED" | "VOIDED"

export interface QuickSaleUser {
  id: number
  username: string
}

export interface QuickSaleLine {
  id: number
  item: {
    id: string
    name: string
    sku: string
  }
  quantity: string
  unit_price: string
  unit_cost: string | null
}

export interface QuickSale {
  id: string
  branch: {
    id: string
    name: string
    code: string
  }
  customer_name: string
  notes: string
  sold_by: QuickSaleUser | null
  sold_at: string
  occurred_at: string
  status: QuickSaleStatus
  voided_by: QuickSaleUser | null
  voided_at: string | null
  total_value: string
  lines: QuickSaleLine[]
}

export interface QuickSaleListResponse {
  results: QuickSale[]
  next: string | null
  previous: string | null
  count: number
}

export interface CreateQuickSaleLinePayload {
  item: string
  quantity: string
  unit_price: string
}

export interface CreateQuickSalePayload {
  branch: string
  customer_name: string
  notes: string
  occurred_at?: string
  lines: CreateQuickSaleLinePayload[]
}
