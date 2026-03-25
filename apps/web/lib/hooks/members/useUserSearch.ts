"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { UserSearchResult } from "@/lib/types/members"

function normalizeSearchResult(result: UserSearchResult): UserSearchResult {
  return {
    id: String(result.id),
    email: result.email,
    first_name: result.first_name ?? "",
    last_name: result.last_name ?? "",
  }
}

export function useUserSearch(orgId: string, email: string) {
  return useQuery({
    queryKey: ["member-search", orgId, email],
    queryFn: async () => {
      const results = await apiRequest<UserSearchResult[]>(
        `orgs/${orgId}/members/search/?email=${encodeURIComponent(email)}`,
      )

      return results.map(normalizeSearchResult)
    },
    enabled: !!orgId && email.trim().length >= 3,
  })
}
