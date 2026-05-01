"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { GoodsReceiptListResponse } from "@/lib/types/goods-receipts"

interface UseGoodsReceiptsParams {
  orgId: string
  receipt_type?: string
  branch?: string
  supplier?: string
  date_after?: string
  date_before?: string
  page?: string
}

export function useGoodsReceipts(params: UseGoodsReceiptsParams) {
  const { orgId, ...filters } = params

  return useQuery<GoodsReceiptListResponse>({
    queryKey: [
      "goods-receipts",
      orgId,
      filters.receipt_type,
      filters.branch,
      filters.supplier,
      filters.date_after,
      filters.date_before,
      filters.page,
    ],
    queryFn: async () => {
      const searchParams = new URLSearchParams()
      if (filters.receipt_type) searchParams.set("receipt_type", filters.receipt_type)
      if (filters.branch) searchParams.set("branch", filters.branch)
      if (filters.supplier) searchParams.set("supplier", filters.supplier)
      if (filters.date_after) searchParams.set("date_after", filters.date_after)
      if (filters.date_before) searchParams.set("date_before", filters.date_before)
      if (filters.page) searchParams.set("page", filters.page)
      const qs = searchParams.toString()

      return apiRequest<GoodsReceiptListResponse>(
        `orgs/${orgId}/goods-receipts/${qs ? `?${qs}` : ""}`,
      )
    },
    enabled: !!orgId,
    placeholderData: (previousData) => previousData,
  })
}
