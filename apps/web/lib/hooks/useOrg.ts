"use client"

import { useParams } from "next/navigation"

import { useAuth } from "./useAuth"

export function useOrg() {
  const params = useParams<{ orgId: string }>()
  const orgId = params?.orgId ?? ""
  const { user } = useAuth()

  const membership = user?.memberships?.find((m) => m.org_id === orgId) ?? null
  const role = membership?.role ?? null
  const orgName = membership?.org_name ?? null
  const isParentUser = user?.is_parent_member ?? false

  const canAccess = (allowedRoles: Array<"OWNER" | "ADMIN" | "STAFF">) => {
    if (isParentUser) return true
    if (!role) return false
    return allowedRoles.includes(role)
  }

  return {
    orgId,
    orgName,
    role,
    membership,
    isParentUser,
    canAccess,
  }
}
