"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"

export interface Membership {
  org_id: string
  org_name: string
  role: "OWNER" | "ADMIN" | "STAFF"
  branch_id: string | null
  branch_name: string | null
}

export interface AuthUser {
  id: string
  email: string
  first_name: string
  last_name: string
  is_superuser: boolean
  is_parent_member: boolean
  parent_role: "PARENT_ADMIN" | "PARENT_VIEWER" | null
  parent_company_id: string | null
  parent_company_name: string | null
  memberships: Membership[]
}

function normalizeAuthUser(user: AuthUser): AuthUser {
  return {
    ...user,
    first_name: user.first_name ?? "",
    last_name: user.last_name ?? "",
    memberships: Array.isArray(user.memberships) ? user.memberships : [],
  }
}

export function useAuth() {
  const { data, isLoading, error } = useQuery<AuthUser>({
    queryKey: ["auth", "me"],
    queryFn: async () => normalizeAuthUser(await apiRequest<AuthUser>("auth/me/")),
    retry: false,
    staleTime: 5 * 60 * 1000,
  })

  return {
    user: data ?? null,
    isLoading,
    isAuthenticated: !!data,
    error,
  }
}
