export interface OrgItem {
  id: string
  organization: string
  master_item: string
  name: string
  name_override: string
  sku: string
  is_active: boolean
  created_at: string
  preferred_supplier: { id: number; display_name: string } | null
}

export interface OrgItemListResponse {
  results: OrgItem[]
  next: string | null
  previous: string | null
  count: number
}

export interface ActivateItemPayload {
  master_item: string
  name?: string
}

export interface UpdateOrgItemPayload {
  name?: string
  is_active?: boolean
}

export interface BulkActivateOrgItemsPayload {
  master_items: string[]
}

export interface BulkActivateOrgItemsResponse {
  activated: number
  already_active: number
  total: number
}
