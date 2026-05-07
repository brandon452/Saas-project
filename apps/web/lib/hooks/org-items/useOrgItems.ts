"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { OrgItemListResponse } from "@/lib/types/org-items"

interface UseOrgItemsParams {
  orgId: string
  search?: string
  is_active: "true" | "false"
  page?: string
  supplier?: string
  has_preferred_supplier?: "true" | "false"
}

export function useOrgItems({ orgId, search, is_active, page, supplier, has_preferred_supplier }: UseOrgItemsParams) {
  return useQuery<OrgItemListResponse>({
    queryKey: ["org-items", orgId, search ?? "", is_active, page ?? "1", supplier ?? "", has_preferred_supplier ?? ""],
    queryFn: () => {
      const params = new URLSearchParams()

      params.set("is_active", is_active)
      params.set("page", page ?? "1")

      if (search) params.set("search", search)
      if (supplier) params.set("supplier", supplier)
      if (has_preferred_supplier) params.set("has_preferred_supplier", has_preferred_supplier)

      return apiRequest<OrgItemListResponse>(`orgs/${orgId}/inventory/items/?${params.toString()}`)
    },
    enabled: !!orgId,
    placeholderData: (previousData) => previousData,
  })
}
