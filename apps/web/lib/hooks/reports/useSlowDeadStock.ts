"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { SlowDeadStockResponse } from "@/lib/types/reports"

interface UseSlowDeadStockParams {
  orgId: string
  branch?: string
  search?: string
  status?: "slow" | "dead" | "all"
  page?: number
}

export function useSlowDeadStock(params: UseSlowDeadStockParams) {
  return useQuery({
    queryKey: [
      "slow-dead-stock",
      params.orgId,
      params.branch ?? "",
      params.search ?? "",
      params.status ?? "all",
      params.page ?? 1,
    ],
    queryFn: async () => {
      const sp = new URLSearchParams()
      if (params.branch) sp.set("branch", params.branch)
      if (params.search) sp.set("search", params.search)
      if (params.status && params.status !== "all") sp.set("status", params.status)
      if (params.page && params.page > 1) sp.set("page", String(params.page))
      const qs = sp.toString()
      return apiRequest<SlowDeadStockResponse>(
        `orgs/${params.orgId}/reports/slow-dead-stock/${qs ? `?${qs}` : ""}`,
      )
    },
    enabled: !!params.orgId,
    placeholderData: (previousData) => previousData,
  })
}
