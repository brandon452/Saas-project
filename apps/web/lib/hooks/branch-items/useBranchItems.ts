"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { PaginatedResponse } from "@/lib/types/purchase-orders"
import type { BranchItemListRow } from "@/lib/types/branch-items"

export function useBranchItems(orgId: string, branchId: string) {
  return useQuery<PaginatedResponse<BranchItemListRow>>({
    queryKey: ["branch-items", orgId, branchId],
    queryFn: () =>
      apiRequest<PaginatedResponse<BranchItemListRow>>(
        `orgs/${orgId}/branch-items/?branch=${branchId}&is_active=true`,
      ),
    enabled: !!orgId && !!branchId,
  })
}
