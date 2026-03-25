"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { BranchCatalogResponse } from "@/lib/types/branch-items"

interface UseBranchItemCatalogParams {
  orgId: string
  branchId: string
  search?: string
  page?: string
}

export function useBranchItemCatalog(params: UseBranchItemCatalogParams) {
  return useQuery({
    queryKey: [
      "branch-catalog",
      params.orgId,
      params.branchId,
      params.search ?? "",
      params.page ?? "1",
    ],
    queryFn: async () => {
      const sp = new URLSearchParams()
      sp.set("branch", params.branchId)
      if (params.search) sp.set("search", params.search)
      if (params.page) sp.set("page", params.page)

      return apiRequest<BranchCatalogResponse>(
        `orgs/${params.orgId}/branch-items/catalog/?${sp.toString()}`,
      )
    },
    enabled: !!params.orgId && !!params.branchId,
  })
}
