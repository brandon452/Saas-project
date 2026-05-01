export interface OrgSettings {
  id: string
  name: string
  slug: string
  parent_company: string
  parent_company_name: string
  is_active: boolean
  created_at: string
  default_currency: string
  default_timezone: string
  allow_negative_stock: boolean
  purchase_order_prefix: string
  purchase_order_next_number: number
  branch_transfer_approval_required: boolean
  stock_take_approval_required: boolean
}

export interface UpdateOrgSettingsPayload {
  name?: string
  default_currency?: string
  default_timezone?: string
  allow_negative_stock?: boolean
  purchase_order_prefix?: string
  purchase_order_next_number?: number
  branch_transfer_approval_required?: boolean
  stock_take_approval_required?: boolean
}
