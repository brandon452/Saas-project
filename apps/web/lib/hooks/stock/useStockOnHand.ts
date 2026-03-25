"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { StockOnHandListResponse } from "@/lib/types/stock"

interface UseStockOnHandParams {
  orgId: string
  branch?: string
  item?: string
  page?: string
}

export function useStockOnHand(params: UseStockOnHandParams) {
  const { orgId, ...filters } = params

  return useQuery<StockOnHandListResponse>({
    queryKey: [
      "stock-on-hand",
      orgId,
      filters.branch,
      filters.item,
      filters.page,
    ],
    queryFn: async () => {
      const sp = new URLSearchParams()
      if (filters.branch) sp.set("branch", filters.branch)
      if (filters.item) sp.set("item", filters.item)
      if (filters.page) sp.set("page", filters.page)
      const qs = sp.toString()

      return apiRequest<StockOnHandListResponse>(
        `orgs/${orgId}/inventory/stock/${qs ? `?${qs}` : ""}`,
      )
    },
    enabled: !!orgId,
  })
}
