"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { getCsrfHeader } from "@/lib/csrf"
import type {
  ActivateItemPayload,
  BulkActivateOrgItemsPayload,
  BulkActivateOrgItemsResponse,
  OrgItem,
  UpdateOrgItemPayload,
} from "@/lib/types/org-items"

export function useOrgItemMutations(orgId: string) {
  const queryClient = useQueryClient()

  const jsonHeaders = {
    "Content-Type": "application/json",
    ...getCsrfHeader(),
  }

  const activateItem = useMutation({
    mutationFn: (payload: ActivateItemPayload) =>
      apiRequest<OrgItem>(`orgs/${orgId}/inventory/items/`, {
        method: "POST",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-items", orgId] })
      queryClient.invalidateQueries({ queryKey: ["org-items", orgId, "available"] })
    },
  })

  const updateOrgItem = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateOrgItemPayload }) =>
      apiRequest<OrgItem>(`orgs/${orgId}/inventory/items/${id}/`, {
        method: "PATCH",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-items", orgId] })
    },
  })

  const deactivateOrgItem = useMutation({
    mutationFn: (id: string) =>
      apiRequest<void>(`orgs/${orgId}/inventory/items/${id}/`, {
        method: "DELETE",
        headers: getCsrfHeader(),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-items", orgId] })
    },
  })

  const bulkActivateItems = useMutation({
    mutationFn: (payload: BulkActivateOrgItemsPayload) =>
      apiRequest<BulkActivateOrgItemsResponse>(`orgs/${orgId}/inventory/items/bulk-activate/`, {
        method: "POST",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-items", orgId] })
      queryClient.invalidateQueries({ queryKey: ["org-items", orgId, "available"] })
    },
  })

  return {
    activateItem,
    updateOrgItem,
    deactivateOrgItem,
    bulkActivateItems,
  }
}
