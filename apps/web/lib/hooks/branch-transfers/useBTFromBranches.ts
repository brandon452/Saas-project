"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { fetchAllPages } from "@/lib/utils/pagination"

export interface BTFromBranch {
  id: string
  name: string
  code: string
}

export function useBTFromBranches(orgId: string) {
  return useQuery<BTFromBranch[]>({
    queryKey: ["bt-from-branches", orgId],
    queryFn: () => fetchAllPages<BTFromBranch>(`orgs/${orgId}/branches/`, apiRequest),
    enabled: !!orgId,
    staleTime: 5 * 60 * 1000,
  })
}
