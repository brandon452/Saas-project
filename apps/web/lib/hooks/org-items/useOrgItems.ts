"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { OrgItemListResponse } from "@/lib/types/org-items"

interface UseOrgItemsParams {
  orgId: string
  search?: string
  is_active: "true" | "false"
  page?: string
}

export function useOrgItems({ orgId, search, is_active, page }: UseOrgItemsParams) {
  return useQuery<OrgItemListResponse>({
    queryKey: ["org-items", orgId, search ?? "", is_active, page ?? "1"],
    queryFn: () => {
      const params = new URLSearchParams()

      params.set("is_active", is_active)
      params.set("page", page ?? "1")

      if (search) {
        params.set("search", search)
      }

      return apiRequest<OrgItemListResponse>(`orgs/${orgId}/inventory/items/?${params.toString()}`)
    },
    enabled: !!orgId,
    placeholderData: (previousData) => previousData,
  })
}
