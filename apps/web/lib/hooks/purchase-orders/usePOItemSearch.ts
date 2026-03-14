"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { Item, PaginatedResponse } from "@/lib/types/purchase-orders"

export function usePOItemSearch(orgId: string, query: string) {
  return useQuery<Item[]>({
    queryKey: ["items", orgId, "search", query],
    queryFn: async () => {
      const page = await apiRequest<PaginatedResponse<Item>>(
        `orgs/${orgId}/inventory/items/?search=${encodeURIComponent(query)}`,
      )
      return page.results
    },
    enabled: !!orgId && query.length >= 2,
    staleTime: 30 * 1000,
  })
}
