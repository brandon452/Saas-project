"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { StockValuationResponse } from "@/lib/types/reports"

interface UseStockValuationParams {
  orgId: string
  branch?: string
  search?: string
  periodId?: string
}

export function useStockValuation(params: UseStockValuationParams) {
  return useQuery({
    queryKey: [
      "stock-valuation",
      params.orgId,
      params.branch ?? "",
      params.search ?? "",
      params.periodId ?? "",
    ],
    queryFn: async () => {
      const sp = new URLSearchParams()
      if (params.branch) sp.set("branch", params.branch)
      if (params.search) sp.set("search", params.search)
      if (params.periodId) sp.set("period_id", params.periodId)
      const qs = sp.toString()
      return apiRequest<StockValuationResponse>(
        `orgs/${params.orgId}/reports/stock-valuation/${qs ? `?${qs}` : ""}`,
      )
    },
    enabled: !!params.orgId,
  })
}
