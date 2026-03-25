"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { AdjustmentItemResult } from "@/lib/types/stock-adjustments"

export function useAdjustmentItemSearch(orgId: string, branchId: string, query: string) {
  return useQuery({
    queryKey: ["adjustment-item-search", orgId, branchId, query],
    queryFn: async () => {
      const res = await apiRequest<{ results: AdjustmentItemResult[] }>(
        `orgs/${orgId}/inventory/items/?search=${encodeURIComponent(query)}`,
        {},
        undefined,
        branchId,
      )
      return res.results
    },
    enabled: !!orgId && !!branchId && query.trim().length >= 2,
    staleTime: 30 * 1000,
  })
}
