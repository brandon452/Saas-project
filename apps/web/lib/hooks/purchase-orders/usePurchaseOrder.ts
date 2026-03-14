"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { PurchaseOrder } from "@/lib/types/purchase-orders"

export function usePurchaseOrder(orgId: string, id: string) {
  return useQuery<PurchaseOrder>({
    queryKey: ["purchase-orders", orgId, id],
    queryFn: () => apiRequest<PurchaseOrder>(`orgs/${orgId}/purchase-orders/${id}/`),
    enabled: !!orgId && !!id,
    staleTime: 30 * 1000,
  })
}
