"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { getCsrfHeader } from "@/lib/csrf"
import type { POLine, PurchaseOrder } from "@/lib/types/purchase-orders"

export function usePOMutations(orgId: string) {
  const queryClient = useQueryClient()

  function invalidateList() {
    queryClient.invalidateQueries({ queryKey: ["purchase-orders", orgId] })
  }

  function invalidateDetail(poId: number) {
    queryClient.invalidateQueries({
      queryKey: ["purchase-orders", orgId, String(poId)],
    })
  }

  function invalidateBoth(poId: number) {
    invalidateList()
    invalidateDetail(poId)
  }

  const createPO = useMutation({
    mutationFn: (data: { supplier: number; branch: number; notes?: string }) =>
      apiRequest<PurchaseOrder>(`orgs/${orgId}/purchase-orders/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getCsrfHeader() },
        body: JSON.stringify(data),
      }),
    onSuccess: () => invalidateList(),
  })

  const submitPO = useMutation({
    mutationFn: (poId: number) =>
      apiRequest<PurchaseOrder>(`orgs/${orgId}/purchase-orders/${poId}/submit/`, {
        method: "POST",
        headers: getCsrfHeader(),
      }),
    onSuccess: (_, poId) => invalidateBoth(poId),
  })

  const cancelPO = useMutation({
    mutationFn: (poId: number) =>
      apiRequest<PurchaseOrder>(`orgs/${orgId}/purchase-orders/${poId}/cancel/`, {
        method: "POST",
        headers: getCsrfHeader(),
      }),
    onSuccess: (_, poId) => invalidateBoth(poId),
  })

  const addLine = useMutation({
    mutationFn: ({
      poId,
      data,
    }: {
      poId: number
      data: { item: number; ordered_quantity: number; unit_price: string }
    }) =>
      apiRequest<POLine>(`orgs/${orgId}/purchase-orders/${poId}/lines/add/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getCsrfHeader() },
        body: JSON.stringify(data),
      }),
    onSuccess: (_, { poId }) => invalidateBoth(poId),
  })

  const updateLine = useMutation({
    mutationFn: ({
      poId,
      lineId,
      data,
    }: {
      poId: number
      lineId: number
      data: Partial<{ ordered_quantity: number; unit_price: string }>
    }) =>
      apiRequest<POLine>(`orgs/${orgId}/purchase-orders/${poId}/lines/${lineId}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...getCsrfHeader() },
        body: JSON.stringify(data),
      }),
    onSuccess: (_, { poId }) => invalidateBoth(poId),
  })

  const removeLine = useMutation({
    mutationFn: ({ poId, lineId }: { poId: number; lineId: number }) =>
      apiRequest(`orgs/${orgId}/purchase-orders/${poId}/lines/${lineId}/remove/`, {
        method: "DELETE",
        headers: getCsrfHeader(),
      }),
    onSuccess: (_, { poId }) => invalidateBoth(poId),
  })

  return { createPO, submitPO, cancelPO, addLine, updateLine, removeLine }
}
