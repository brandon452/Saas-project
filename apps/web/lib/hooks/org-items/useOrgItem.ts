"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { OrgItem } from "@/lib/types/org-items"

export function useOrgItem(orgId: string, itemId: string) {
  return useQuery<OrgItem>({
    queryKey: ["org-item", orgId, itemId],
    queryFn: () => apiRequest<OrgItem>(`orgs/${orgId}/inventory/items/${itemId}/`),
    enabled: !!orgId && !!itemId,
  })
}
