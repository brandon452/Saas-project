"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { BTItemSearchResponse } from "@/lib/types/branch-transfers"

export function useBTItemSearch(orgId: string, query: string) {
  return useQuery<BTItemSearchResponse>({
    queryKey: ["bt-item-search", orgId, query],
    queryFn: () =>
      apiRequest<BTItemSearchResponse>(
        `orgs/${orgId}/inventory/items/?search=${encodeURIComponent(query)}`,
      ),
    enabled: !!orgId && query.trim().length >= 2,
  })
}
