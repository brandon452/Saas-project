"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { Item, PaginatedResponse } from "@/lib/types/purchase-orders"
import { toRelativePath } from "@/lib/utils/pagination"

export function usePOItemNames(orgId: string, itemIds: string[]) {
  const stableIds = [...new Set(itemIds)].sort()

  return useQuery<Record<string, Item>>({
    queryKey: ["items", orgId, "resolve", stableIds.join(",")],
    queryFn: async () => {
      const unresolved = new Set(stableIds)
      const resolved: Record<string, Item> = {}
      let nextPath: string | null = `orgs/${orgId}/inventory/items/`

      while (nextPath && unresolved.size > 0) {
        const response: PaginatedResponse<Item> = await apiRequest<PaginatedResponse<Item>>(nextPath)
        for (const item of response.results) {
          if (unresolved.has(item.id)) {
            resolved[item.id] = item
            unresolved.delete(item.id)
          }
        }
        nextPath = response.next ? toRelativePath(response.next) : null
      }

      return resolved
    },
    enabled: !!orgId && stableIds.length > 0,
    staleTime: 5 * 60 * 1000,
  })
}
