export type POStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "PARTIALLY_RECEIVED"
  | "FULLY_RECEIVED"
  | "CANCELLED"

export interface POLine {
  id: number
  item: number
  ordered_quantity: number
  unit_price: string
  received_quantity: number | null
}

export interface PurchaseOrder {
  id: number
  po_number: string
  supplier: number
  branch: number
  status: POStatus
  notes: string
  lines: POLine[]
  created_by: number | null
  created_at: string
  updated_at: string
}

export interface Supplier {
  id: number
  name: string
  is_active: boolean
}

export interface Branch {
  id: number
  name: string
  code: string
}

export interface Item {
  id: number
  name: string
  sku: string
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
