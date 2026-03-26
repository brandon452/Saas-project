export interface BranchCatalogRow {
  id: string
  name: string
  sku: string
  is_enabled: boolean
  branch_item_id: number | null
}

export interface BranchCatalogResponse {
  results: BranchCatalogRow[]
  next: string | null
  previous: string | null
  count: number
}

export interface EnableBranchItemPayload {
  org_item: string
  branch: string
}

export interface BulkActivatePayload {
  branch: string
  org_items: string[]
}

export interface BulkActivateResponse {
  activated: number
  already_active: number
  total: number
}
