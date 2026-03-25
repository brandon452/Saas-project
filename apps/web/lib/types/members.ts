export type MemberRole = "OWNER" | "ADMIN" | "STAFF"

export interface MemberUser {
  id: string
  email: string
  first_name: string
  last_name: string
}

export interface MemberBranch {
  id: string
  name: string
  code: string
}

export interface Member {
  id: number
  user: MemberUser
  role: MemberRole
  is_active: boolean
  organization: string
  assigned_branch: MemberBranch | null
}

export interface AddMemberPayload {
  user_id: string
  role: MemberRole
  assigned_branch?: string
}

export interface UpdateMemberPayload {
  role?: MemberRole
  is_active?: boolean
  assigned_branch?: string | null
}

export interface UserSearchResult {
  id: string
  email: string
  first_name: string
  last_name: string
}
