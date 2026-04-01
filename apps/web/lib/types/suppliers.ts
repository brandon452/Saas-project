export interface SupplierContact {
  id: number
  full_name: string
  role: string
  email: string
  phone: string
  is_primary: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Supplier {
  id: number
  display_name: string
  name: string // Phase 1 alias for display_name — remove in Phase 3
  code: string
  legal_name: string
  email: string
  phone: string
  payment_terms_days: number | null
  default_lead_time_days: number | null
  currency: string
  tax_id: string
  address_line1: string
  address_line2: string
  city: string
  state: string
  postal_code: string
  country: string
  notes: string
  is_active: boolean
  contacts: SupplierContact[]
  created_at: string
  updated_at: string
}
