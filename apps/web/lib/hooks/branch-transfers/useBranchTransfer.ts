"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { BranchTransfer } from "@/lib/types/branch-transfers"

export function useBranchTransfer(orgId: string, id: string) {
  return useQuery<BranchTransfer>({
    queryKey: ["branch-transfers", orgId, id],
    queryFn: () => apiRequest<BranchTransfer>(`orgs/${orgId}/branch-transfers/${id}/`),
    enabled: !!orgId && !!id,
  })
}
