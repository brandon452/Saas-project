"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { StockItemSearchResponse } from "@/lib/types/stock"

export function useStockItemSearch(
  orgId: string,
  query: string,
  branchId?: string,
) {
  return useQuery<StockItemSearchResponse>({
    queryKey: ["stock-item-search", orgId, query, branchId],
    queryFn: () =>
      apiRequest<StockItemSearchResponse>(
        `orgs/${orgId}/inventory/items/?search=${encodeURIComponent(query)}`,
        {},
        undefined,
        branchId,
      ),
    enabled: !!orgId && query.trim().length >= 2,
  })
}
