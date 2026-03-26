"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { getCsrfHeader } from "@/lib/csrf"
import type { BulkActivatePayload, BulkActivateResponse, BulkDeactivatePayload, BulkDeactivateResponse, EnableBranchItemPayload } from "@/lib/types/branch-items"

export function useBranchItemMutations(orgId: string, branchId: string) {
  const queryClient = useQueryClient()

  const jsonHeaders = {
    "Content-Type": "application/json",
    ...getCsrfHeader(),
  }

  const enableBranchItem = useMutation({
    mutationFn: (payload: EnableBranchItemPayload) =>
      apiRequest<unknown>(`orgs/${orgId}/branch-items/`, {
        method: "POST",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["branch-catalog", orgId, branchId],
      })
    },
  })

  const disableBranchItem = useMutation({
    mutationFn: (branchItemId: number) =>
      apiRequest<void>(`orgs/${orgId}/branch-items/${branchItemId}/`, {
        method: "DELETE",
        headers: getCsrfHeader(),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["branch-catalog", orgId, branchId],
      })
    },
  })

  const bulkActivateBranchItems = useMutation({
    mutationFn: (payload: BulkActivatePayload) =>
      apiRequest<BulkActivateResponse>(
        `orgs/${orgId}/branch-items/bulk-activate/`,
        {
          method: "POST",
          headers: jsonHeaders,
          body: JSON.stringify(payload),
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["branch-catalog", orgId, branchId],
      })
    },
  })

  const bulkDeactivateBranchItems = useMutation({
    mutationFn: (payload: BulkDeactivatePayload) =>
      apiRequest<BulkDeactivateResponse>(
        `orgs/${orgId}/branch-items/bulk-deactivate/`,
        {
          method: "POST",
          headers: jsonHeaders,
          body: JSON.stringify(payload),
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["branch-catalog", orgId, branchId],
      })
    },
  })

  return { enableBranchItem, disableBranchItem, bulkActivateBranchItems, bulkDeactivateBranchItems }
}
