export type ReceiptType = "PO_RECEIPT" | "DIRECT_RECEIPT"

export interface GoodsReceiptItem {
  id: string
  name: string
  sku: string
}

export interface GoodsReceiptLine {
  id: string
  po_line: string | null
  item: GoodsReceiptItem | null
  quantity_received: number
  unit_cost: string | null
}

export interface GoodsReceipt {
  id: string
  receipt_type: ReceiptType
  purchase_order: string | null
  branch: string
  supplier: string | null
  source_reference: string
  received_by: string | null
  received_at: string
  notes: string
  lines: GoodsReceiptLine[]
}

export type GoodsReceiptListItem = GoodsReceipt

export interface GoodsReceiptListResponse {
  results: GoodsReceiptListItem[]
  next: string | null
  previous: string | null
  count: number
}

export interface POReceiptLineInput {
  po_line: string
  quantity_received: number
  unit_cost: string | null
}

export interface DirectReceiptLineInput {
  item: string
  quantity_received: number
  unit_cost: string
}

export interface CreatePOReceiptPayload {
  receipt_type: "PO_RECEIPT"
  purchase_order: string
  notes: string
  lines: POReceiptLineInput[]
}

export interface CreateDirectReceiptPayload {
  receipt_type: "DIRECT_RECEIPT"
  branch: string
  supplier: string | null
  source_reference: string
  notes: string
  lines: DirectReceiptLineInput[]
}
