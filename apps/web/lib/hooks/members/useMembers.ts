"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { fetchAllPages } from "@/lib/utils/pagination"
import type { Member } from "@/lib/types/members"

interface RawMemberUser {
  id: string
  email: string
  first_name?: string | null
  last_name?: string | null
}

interface RawMemberBranch {
  id: string | number
  name: string
  code: string
}

interface RawMember {
  id: number
  user: RawMemberUser
  role: "OWNER" | "ADMIN" | "STAFF"
  is_active: boolean
  organization: string | number
  assigned_branch: RawMemberBranch | null
}

export interface UseMembersParams {
  orgId: string
  is_active?: string
}

function normalizeMember(member: RawMember): Member {
  return {
    id: member.id,
    user: {
      id: String(member.user.id),
      email: member.user.email,
      first_name: member.user.first_name ?? "",
      last_name: member.user.last_name ?? "",
    },
    role: member.role,
    is_active: member.is_active,
    organization: String(member.organization),
    assigned_branch: member.assigned_branch
      ? {
          id: String(member.assigned_branch.id),
          name: member.assigned_branch.name,
          code: member.assigned_branch.code,
        }
      : null,
  }
}

export function useMembers({ orgId, is_active }: UseMembersParams) {
  return useQuery<Member[]>({
    queryKey: ["members", orgId, is_active ?? "all"],
    queryFn: async () => {
      const params = new URLSearchParams()

      if (is_active) {
        params.set("is_active", is_active)
      }

      const path = params.toString()
        ? `orgs/${orgId}/members/?${params.toString()}`
        : `orgs/${orgId}/members/`

      const members = await fetchAllPages<RawMember>(path, apiRequest)
      return members.map(normalizeMember)
    },
    enabled: !!orgId,
  })
}
