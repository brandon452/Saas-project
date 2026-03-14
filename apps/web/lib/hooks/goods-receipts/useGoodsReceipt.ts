"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { GoodsReceipt } from "@/lib/types/goods-receipts"

export function useGoodsReceipt(orgId: string, id: string) {
  return useQuery<GoodsReceipt>({
    queryKey: ["goods-receipts", orgId, id],
    queryFn: () => apiRequest<GoodsReceipt>(`orgs/${orgId}/goods-receipts/${id}/`),
    enabled: !!orgId && !!id,
  })
}
