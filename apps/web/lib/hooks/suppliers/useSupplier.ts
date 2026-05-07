"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { Supplier } from "@/lib/types/suppliers"

export function useSupplier(orgId: string, id: string) {
  return useQuery<Supplier>({
    queryKey: ["suppliers", orgId, id],
    queryFn: () => apiRequest<Supplier>(`orgs/${orgId}/suppliers/${id}/`),
    enabled: !!orgId && !!id,
    staleTime: 30 * 1000,
  })
}
