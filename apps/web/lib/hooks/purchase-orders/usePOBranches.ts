"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { Branch } from "@/lib/types/purchase-orders"
import { fetchAllPages } from "@/lib/utils/pagination"

export function usePOBranches(orgId: string) {
  return useQuery<Branch[]>({
    queryKey: ["branches", orgId, "all"],
    queryFn: () => fetchAllPages<Branch>(`orgs/${orgId}/branches/`, apiRequest),
    enabled: !!orgId,
    staleTime: 5 * 60 * 1000,
  })
}
