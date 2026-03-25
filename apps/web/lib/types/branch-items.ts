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
