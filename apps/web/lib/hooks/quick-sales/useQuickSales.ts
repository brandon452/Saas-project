"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { QuickSaleListResponse } from "@/lib/types/quick-sales"

interface UseQuickSalesParams {
  orgId: string
  branch?: string
  status?: string
  from_date?: string
  to_date?: string
  page?: string
}

export function useQuickSales(params: UseQuickSalesParams) {
  return useQuery<QuickSaleListResponse>({
    queryKey: [
      "quick-sales",
      params.orgId,
      params.branch ?? "",
      params.status ?? "",
      params.from_date ?? "",
      params.to_date ?? "",
      params.page ?? "1",
    ],
    queryFn: async () => {
      const searchParams = new URLSearchParams()
      if (params.branch) searchParams.set("branch", params.branch)
      if (params.status) searchParams.set("status", params.status)
      if (params.from_date) searchParams.set("from_date", params.from_date)
      if (params.to_date) searchParams.set("to_date", params.to_date)
      if (params.page) searchParams.set("page", params.page)
      const qs = searchParams.toString()

      return apiRequest<QuickSaleListResponse>(
        `orgs/${params.orgId}/quick-sales/${qs ? `?${qs}` : ""}`,
      )
    },
    enabled: !!params.orgId,
    placeholderData: (previousData) => previousData,
  })
}
