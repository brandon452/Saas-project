"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { NetworkBranch } from "@/lib/types/branch-transfers"

export function useNetworkBranches(orgId: string) {
  return useQuery<NetworkBranch[]>({
    queryKey: ["network-branches", orgId],
    queryFn: () => apiRequest<NetworkBranch[]>(`orgs/${orgId}/network-branches/`),
    enabled: !!orgId,
  })
}
