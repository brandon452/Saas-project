export type POStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "PARTIALLY_RECEIVED"
  | "FULLY_RECEIVED"
  | "CANCELLED"

export interface POLineItem {
  id: string
  name: string
  sku: string
}

export interface POLine {
  id: number
  item: POLineItem
  ordered_quantity: number
  unit_price: string
  received_quantity: number | null
}

export interface POReceiptSummary {
  id: string
  received_at: string
  received_by: string | null
  line_count: number
  total_quantity_received: number
}

export interface PurchaseOrder {
  id: string
  po_number: string
  supplier: string
  branch: string
  status: POStatus
  notes: string
  lines: POLine[]
  receipts: POReceiptSummary[]
  created_by: number | null
  created_at: string
  updated_at: string
}

export type { Supplier } from "./suppliers"

export interface Branch {
  id: string
  name: string
  code: string
}

export interface Item {
  id: string
  name: string
  sku: string
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
