"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { MasterItemListResponse } from "@/lib/types/master-items"

export function useAvailableMasterItemsPage(
  orgId: string,
  page: number,
  search: string,
) {
  return useQuery({
    queryKey: ["org-items", orgId, "available", page, search],
    queryFn: () => {
      const params = new URLSearchParams({ page: String(page) })
      if (search) params.set("search", search)
      return apiRequest<MasterItemListResponse>(`orgs/${orgId}/master-items/?${params}`)
    },
    enabled: !!orgId,
  })
}
