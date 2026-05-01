"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { CostTrendResponse } from "@/lib/types/reports"

interface UsePurchaseCostTrendParams {
  orgId: string
  item: string
  from_date?: string
  to_date?: string
  supplier?: string
  branch?: string
}

export function usePurchaseCostTrend(params: UsePurchaseCostTrendParams) {
  return useQuery({
    queryKey: [
      "purchase-cost-trend",
      params.orgId,
      params.item,
      params.from_date ?? "",
      params.to_date ?? "",
      params.supplier ?? "",
      params.branch ?? "",
    ],
    queryFn: async () => {
      const sp = new URLSearchParams()
      sp.set("item", params.item)
      if (params.from_date) sp.set("from_date", params.from_date)
      if (params.to_date) sp.set("to_date", params.to_date)
      if (params.supplier) sp.set("supplier", params.supplier)
      if (params.branch) sp.set("branch", params.branch)

      return apiRequest<CostTrendResponse>(
        `orgs/${params.orgId}/reports/purchase-cost-trend/?${sp.toString()}`,
      )
    },
    enabled: !!params.orgId && !!params.item,
    placeholderData: (previousData) => previousData,
  })
}
