"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { fetchAllPages } from "@/lib/utils/pagination"

export interface GRSupplier {
  id: string
  name: string
}

export function useGRSuppliers(orgId: string) {
  return useQuery<GRSupplier[]>({
    queryKey: ["gr-suppliers", orgId],
    queryFn: () => fetchAllPages<GRSupplier>(`orgs/${orgId}/suppliers/?is_active=true`, apiRequest),
    enabled: !!orgId,
  })
}
