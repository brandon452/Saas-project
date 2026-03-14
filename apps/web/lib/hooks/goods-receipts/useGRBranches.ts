"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { fetchAllPages } from "@/lib/utils/pagination"

export interface GRBranch {
  id: string
  name: string
}

export function useGRBranches(orgId: string) {
  return useQuery<GRBranch[]>({
    queryKey: ["gr-branches", orgId],
    queryFn: () => fetchAllPages<GRBranch>(`orgs/${orgId}/branches/`, apiRequest),
    enabled: !!orgId,
  })
}
