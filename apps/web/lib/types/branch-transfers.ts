export interface TransferUser {
  id: number
  username: string
}

export type TransferStatus =
  | "DRAFT"
  | "APPROVED"
  | "IN_TRANSIT"
  | "RECEIVED_COMPLETE"
  | "RECEIVED_WITH_VARIANCE"
  | "CANCELLED"

export type TransferDirection = "Outbound" | "Inbound" | "Internal"

export interface BranchTransferItem {
  id: string
  name: string
  sku: string
}

export interface BranchTransferLine {
  id: number
  item: BranchTransferItem
  quantity_sent: number
  quantity_received: number | null
}

export interface BranchTransfer {
  id: string
  organization: string
  from_branch: string
  to_branch: string
  to_organization: string
  status: TransferStatus
  notes: string
  receive_notes: string
  lines: BranchTransferLine[]
  created_by: TransferUser | null
  approved_by: TransferUser | null
  dispatched_by: TransferUser | null
  dispatched_at: string | null
  received_by: TransferUser | null
  received_at: string | null
  created_at: string
  updated_at: string
}

export type BranchTransferListItem = BranchTransfer

export interface BranchTransferListResponse {
  results: BranchTransferListItem[]
  next: string | null
  previous: string | null
  count: number
}

export interface NetworkBranch {
  id: string
  name: string
  org_id: string
  org_name: string
}

export interface TransferLineInput {
  item: string
  quantity_sent: number
}

export interface CreateTransferPayload {
  from_branch: string
  to_branch: string
  notes: string
  lines: TransferLineInput[]
}

export interface ReceiveLineInput {
  line_id: number
  quantity_received: number
}

export interface ReceiveTransferPayload {
  lines: ReceiveLineInput[]
  notes: string
  idempotency_key?: string
}

export interface BTItemSearchResult {
  id: string
  name: string
  sku: string
}

export interface BTItemSearchResponse {
  results: BTItemSearchResult[]
  next: string | null
}
