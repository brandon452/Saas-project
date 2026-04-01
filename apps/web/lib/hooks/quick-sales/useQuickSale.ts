"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { QuickSale } from "@/lib/types/quick-sales"

interface UseQuickSaleParams {
  orgId: string
  saleId: string
}

export function useQuickSale({ orgId, saleId }: UseQuickSaleParams) {
  return useQuery<QuickSale>({
    queryKey: ["quick-sale", orgId, saleId],
    queryFn: () => apiRequest<QuickSale>(`orgs/${orgId}/quick-sales/${saleId}/`),
    enabled: !!orgId && !!saleId,
  })
}
