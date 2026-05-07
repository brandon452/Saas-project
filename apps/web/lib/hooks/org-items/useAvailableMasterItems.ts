"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { MasterItem, MasterItemListResponse } from "@/lib/types/master-items"

export function useAvailableMasterItems(orgId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["org-items", orgId, "available"],
    queryFn: async (): Promise<MasterItem[]> => {
      const MAX_PAGES = 50 // safety cap: 50 × 100 = 5 000 items
      const all: MasterItem[] = []
      let pageNum = 1

      while (true) {
        const result = await apiRequest<MasterItemListResponse>(
          `orgs/${orgId}/master-items/?page=${pageNum}`,
        )
        all.push(...result.results)
        if (!result.next) break
        if (pageNum >= MAX_PAGES) {
          console.error("[useAvailableMasterItems] page cap exceeded", { orgId, pageNum })
          throw new Error("Catalog too large to load at once. Please contact support.")
        }
        pageNum++
      }

      return all
    },
    enabled: !!orgId && enabled,
  })
}
