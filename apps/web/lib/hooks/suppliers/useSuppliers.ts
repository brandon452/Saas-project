"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { PaginatedResponse } from "@/lib/types/purchase-orders"
import type { Supplier } from "@/lib/types/suppliers"

interface UseSuppliersParams {
  orgId: string
  page?: number
  search?: string
  isActive?: boolean | null
}

export function useSuppliers({ orgId, page = 1, search, isActive }: UseSuppliersParams) {
  return useQuery<PaginatedResponse<Supplier>>({
    queryKey: ["suppliers", orgId, "list", page, search, isActive],
    queryFn: () => {
      const params = new URLSearchParams()
      params.set("page", String(page))

      if (search) params.set("search", search)
      if (isActive !== null && isActive !== undefined) {
        params.set("is_active", String(isActive))
      }

      return apiRequest<PaginatedResponse<Supplier>>(`orgs/${orgId}/suppliers/?${params.toString()}`)
    },
    enabled: !!orgId,
    staleTime: 30 * 1000,
  })
}
