"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiRequest, getApiErrorMessage } from "@/lib/api"
import { getCsrfHeader } from "@/lib/csrf"
import type { CreateQuickSalePayload, QuickSale } from "@/lib/types/quick-sales"

export function useCreateQuickSale(orgId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: CreateQuickSalePayload) => {
      try {
        return await apiRequest<QuickSale>(`orgs/${orgId}/quick-sales/`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...getCsrfHeader() },
          body: JSON.stringify(payload),
        })
      } catch (error) {
        throw new Error(getApiErrorMessage(error, "Failed to create the quick sale."))
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quick-sales", orgId] })
    },
  })
}

export function useVoidQuickSale(orgId: string, saleId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      try {
        return await apiRequest<QuickSale>(`orgs/${orgId}/quick-sales/${saleId}/void/`, {
          method: "POST",
          headers: { ...getCsrfHeader() },
        })
      } catch (error) {
        throw new Error(getApiErrorMessage(error, "Failed to void the quick sale."))
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quick-sales", orgId] })
      queryClient.invalidateQueries({ queryKey: ["quick-sale", orgId, saleId] })
    },
  })
}
