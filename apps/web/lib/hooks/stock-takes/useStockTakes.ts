"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { PaginatedResponse } from "@/lib/types/purchase-orders"
import type { StockTake } from "@/lib/types/stock-takes"

interface UseStockTakesFilters {
  page?: string
}

export function useStockTakes(orgId: string, filters: UseStockTakesFilters) {
  return useQuery<PaginatedResponse<StockTake>>({
    queryKey: ["stock-takes", orgId, filters.page ?? "1"],
    queryFn: () => {
      const params = new URLSearchParams()
      if (filters.page) params.set("page", filters.page)
      const qs = params.toString()

      return apiRequest<PaginatedResponse<StockTake>>(
        `orgs/${orgId}/stock-takes/${qs ? `?${qs}` : ""}`,
      )
    },
    enabled: !!orgId,
  })
}
