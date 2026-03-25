"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { Branch } from "@/lib/types/branches"
import { toRelativePath } from "@/lib/utils/pagination"

interface PaginatedBranchesResponse {
  results: Branch[]
  next: string | null
}

export function useBranches(orgId: string) {
  return useQuery<Branch[]>({
    queryKey: ["branches", orgId],
    queryFn: async () => {
      const response = await apiRequest<Branch[] | PaginatedBranchesResponse>(
        `orgs/${orgId}/branches/`,
      )

      if (Array.isArray(response)) {
        return response
      }

      const branches = [...response.results]
      let nextPath = response.next ? toRelativePath(response.next) : null

      while (nextPath) {
        const nextResponse = await apiRequest<PaginatedBranchesResponse>(nextPath)
        branches.push(...nextResponse.results)
        nextPath = nextResponse.next ? toRelativePath(nextResponse.next) : null
      }

      return branches
    },
    enabled: !!orgId,
  })
}
