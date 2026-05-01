"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { BranchTransferListResponse } from "@/lib/types/branch-transfers"

export function useBranchTransfers(params: {
  orgId: string
  status?: string
  page?: string
}) {
  return useQuery<BranchTransferListResponse>({
    queryKey: ["branch-transfers", params.orgId, params.status, params.page],
    queryFn: async () => {
      const sp = new URLSearchParams()
      if (params.status) sp.set("status", params.status)
      if (params.page) sp.set("page", params.page)
      const qs = sp.toString()

      return apiRequest<BranchTransferListResponse>(
        `orgs/${params.orgId}/branch-transfers/${qs ? `?${qs}` : ""}`,
      )
    },
    enabled: !!params.orgId,
    placeholderData: (previousData) => previousData,
  })
}
