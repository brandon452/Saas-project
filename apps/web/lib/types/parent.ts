export interface ParentOrganization {
  id: string
  name: string
  slug: string
  parent_company?: string
  parent_company_name?: string
}

export type ParentMemberRole = "PARENT_ADMIN" | "PARENT_VIEWER"

export interface ParentMember {
  id: number
  user: {
    id: string
    username: string
    email: string
  }
  parent_company: string
  parent_company_name: string
  role: ParentMemberRole
  is_active: boolean
  created_at: string
  created_by: {
    id: string
    username: string
    email: string
  } | null
}
