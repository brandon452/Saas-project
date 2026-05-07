"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { getCsrfHeader } from "@/lib/csrf"
import type { SupplierCatalogItem } from "@/lib/types/supplier-catalog"

export function useSupplierItems(orgId: string, supplierId: string | null | undefined) {
  return useQuery<SupplierCatalogItem[]>({
    queryKey: ["supplier-items", orgId, supplierId],
    queryFn: () =>
      apiRequest<SupplierCatalogItem[]>(
        `orgs/${orgId}/suppliers/${supplierId}/items/`,
      ),
    enabled: !!orgId && !!supplierId,
    staleTime: 60 * 1000,
  })
}

export function useSupplierItemMutations(orgId: string, supplierId: string) {
  const queryClient = useQueryClient()

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["supplier-items", orgId, supplierId] })
  }

  const addItem = useMutation({
    mutationFn: (data: {
      org_item_id: string
      is_preferred?: boolean
      unit_cost?: string | null
      lead_time_days?: number | null
    }) =>
      apiRequest<SupplierCatalogItem>(`orgs/${orgId}/suppliers/${supplierId}/items/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getCsrfHeader() },
        body: JSON.stringify(data),
      }),
    onSuccess: invalidate,
  })

  const updateItem = useMutation({
    mutationFn: ({
      supplierItemId,
      data,
    }: {
      supplierItemId: number
      data: Partial<{
        is_preferred: boolean
        unit_cost: string | null
        lead_time_days: number | null
      }>
    }) =>
      apiRequest<SupplierCatalogItem>(
        `orgs/${orgId}/suppliers/${supplierId}/items/${supplierItemId}/`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json", ...getCsrfHeader() },
          body: JSON.stringify(data),
        },
      ),
    onSuccess: invalidate,
  })

  const removeItem = useMutation({
    mutationFn: (supplierItemId: number) =>
      apiRequest(
        `orgs/${orgId}/suppliers/${supplierId}/items/${supplierItemId}/`,
        { method: "DELETE", headers: getCsrfHeader() },
      ),
    onSuccess: invalidate,
  })

  return { addItem, updateItem, removeItem }
}
