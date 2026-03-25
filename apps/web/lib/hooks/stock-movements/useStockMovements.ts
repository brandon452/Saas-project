"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { StockMovementsResponse } from "@/lib/types/stock-adjustments"

interface UseStockMovementsParams {
  orgId: string
  branch?: string
  item?: string
  movement_type?: string
  from_date?: string
  to_date?: string
  ordering?: string
  page?: string
}

export function useStockMovements(params: UseStockMovementsParams) {
  return useQuery({
    queryKey: [
      "stock-movements",
      params.orgId,
      params.branch ?? "",
      params.item ?? "",
      params.movement_type ?? "",
      params.from_date ?? "",
      params.to_date ?? "",
      params.ordering ?? "",
      params.page ?? "1",
    ],
    queryFn: async () => {
      const sp = new URLSearchParams()
      if (params.branch) sp.set("branch", params.branch)
      if (params.item) sp.set("item", params.item)
      if (params.movement_type) sp.set("movement_type", params.movement_type)
      if (params.from_date) sp.set("from_date", params.from_date)
      if (params.to_date) sp.set("to_date", params.to_date)
      if (params.ordering) sp.set("ordering", params.ordering)
      if (params.page) sp.set("page", params.page)
      const qs = sp.toString()

      return apiRequest<StockMovementsResponse>(
        `orgs/${params.orgId}/inventory/movements/${qs ? `?${qs}` : ""}`,
      )
    },
    enabled: !!params.orgId,
    placeholderData: (previousData) => previousData,
  })
}
