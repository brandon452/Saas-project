"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { MasterItem } from "@/lib/types/master-items"

export function useAvailableMasterItems(orgId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["org-items", orgId, "available"],
    queryFn: () => apiRequest<MasterItem[]>(`orgs/${orgId}/master-items/`),
    enabled: !!orgId && enabled,
  })
}
