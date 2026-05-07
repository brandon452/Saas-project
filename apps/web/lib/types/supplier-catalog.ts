export interface SupplierCatalogItem {
  id: number
  org_item: { id: string; name: string; sku: string }
  is_preferred: boolean
  unit_cost: string | null
  lead_time_days: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}
