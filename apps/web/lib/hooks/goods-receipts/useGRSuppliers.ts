"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { Supplier } from "@/lib/types/suppliers"
import { fetchAllPages } from "@/lib/utils/pagination"

export function useGRSuppliers(orgId: string) {
  return useQuery<Supplier[]>({
    queryKey: ["gr-suppliers", orgId],
    queryFn: () => fetchAllPages<Supplier>(`orgs/${orgId}/suppliers/?is_active=true`, apiRequest),
    enabled: !!orgId,
    staleTime: 5 * 60 * 1000,
  })
}
