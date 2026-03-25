"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { getCsrfHeader } from "@/lib/csrf"
import type {
  Branch,
  CreateBranchPayload,
  UpdateBranchPayload,
} from "@/lib/types/branches"

export function useBranchMutations(orgId: string) {
  const queryClient = useQueryClient()

  const jsonHeaders = {
    "Content-Type": "application/json",
    ...getCsrfHeader(),
  }

  function invalidateBranches() {
    queryClient.invalidateQueries({ queryKey: ["branches", orgId] })
  }

  const createBranch = useMutation({
    mutationFn: (payload: CreateBranchPayload) =>
      apiRequest<Branch>(`orgs/${orgId}/branches/`, {
        method: "POST",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
      }),
    onSuccess: invalidateBranches,
  })

  const updateBranch = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateBranchPayload }) =>
      apiRequest<Branch>(`orgs/${orgId}/branches/${id}/`, {
        method: "PATCH",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
      }),
    onSuccess: invalidateBranches,
  })

  return {
    createBranch,
    updateBranch,
  }
}
