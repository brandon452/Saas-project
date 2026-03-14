"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { Supplier } from "@/lib/types/purchase-orders"
import { fetchAllPages } from "@/lib/utils/pagination"

export function usePOSuppliers(orgId: string) {
  return useQuery<Supplier[]>({
    queryKey: ["suppliers", orgId, "all"],
    queryFn: () => fetchAllPages<Supplier>(`orgs/${orgId}/suppliers/?is_active=true`, apiRequest),
    enabled: !!orgId,
    staleTime: 5 * 60 * 1000,
  })
}
