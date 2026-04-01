"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { SupplierContact } from "@/lib/types/suppliers"

export function useSupplierContacts(orgId: string, supplierId: number | null) {
  return useQuery<SupplierContact[]>({
    queryKey: ["supplier-contacts", orgId, supplierId],
    queryFn: () =>
      apiRequest<SupplierContact[]>(`orgs/${orgId}/suppliers/${supplierId}/contacts/`),
    enabled: !!orgId && supplierId !== null,
    staleTime: 30 * 1000,
  })
}
