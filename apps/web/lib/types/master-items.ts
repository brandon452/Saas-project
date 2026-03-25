export interface MasterItem {
  id: string
  name: string
  sku: string
  is_active: boolean
  created_at: string
}

export interface MasterItemListResponse {
  results: MasterItem[]
  next: string | null
  previous: string | null
  count: number
}

export interface CreateMasterItemPayload {
  name: string
  sku: string
}

export interface UpdateMasterItemPayload {
  name?: string
  sku?: string
  is_active?: boolean
}
