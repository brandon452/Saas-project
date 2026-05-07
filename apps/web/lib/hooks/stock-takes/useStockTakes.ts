"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { PaginatedResponse } from "@/lib/types/purchase-orders"
import type { StockTake } from "@/lib/types/stock-takes"

interface UseStockTakesFilters {
  page?: string
  stock_take_type?: string
  cycle_item_class?: string
}

export function useStockTakes(orgId: string, filters: UseStockTakesFilters) {
  return useQuery<PaginatedResponse<StockTake>>({
    queryKey: [
      "stock-takes",
      orgId,
      filters.page ?? "1",
      filters.stock_take_type ?? "",
      filters.cycle_item_class ?? "",
    ],
    queryFn: () => {
      const params = new URLSearchParams()
      if (filters.page) params.set("page", filters.page)
      if (filters.stock_take_type) params.set("stock_take_type", filters.stock_take_type)
      if (filters.cycle_item_class) params.set("cycle_item_class", filters.cycle_item_class)
      const qs = params.toString()

      return apiRequest<PaginatedResponse<StockTake>>(
        `orgs/${orgId}/stock-takes/${qs ? `?${qs}` : ""}`,
      )
    },
    enabled: !!orgId,
    placeholderData: (previousData) => previousData,
  })
}
