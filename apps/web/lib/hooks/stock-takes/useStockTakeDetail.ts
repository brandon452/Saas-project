"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { StockTakeDetail } from "@/lib/types/stock-takes"

export function useStockTakeDetail(orgId: string, stockTakeId: string) {
  return useQuery<StockTakeDetail>({
    queryKey: ["stock-takes", orgId, "detail", stockTakeId],
    queryFn: () => apiRequest<StockTakeDetail>(`orgs/${orgId}/stock-takes/${stockTakeId}/`),
    enabled: !!orgId && !!stockTakeId,
  })
}
