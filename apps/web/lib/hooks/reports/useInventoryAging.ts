"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { InventoryAgingResponse } from "@/lib/types/reports"

interface UseInventoryAgingParams {
  orgId: string
  branch?: string
  search?: string
  page?: number
}

export function useInventoryAging(params: UseInventoryAgingParams) {
  return useQuery({
    queryKey: [
      "inventory-aging",
      params.orgId,
      params.branch ?? "",
      params.search ?? "",
      params.page ?? 1,
    ],
    queryFn: async () => {
      const sp = new URLSearchParams()
      if (params.branch) sp.set("branch", params.branch)
      if (params.search) sp.set("search", params.search)
      if (params.page && params.page > 1) sp.set("page", String(params.page))
      const qs = sp.toString()
      return apiRequest<InventoryAgingResponse>(
        `orgs/${params.orgId}/reports/inventory-aging/${qs ? `?${qs}` : ""}`,
      )
    },
    enabled: !!params.orgId,
    placeholderData: (previousData) => previousData,
  })
}
