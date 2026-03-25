"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { getCsrfHeader } from "@/lib/csrf"
import type { AddMemberPayload, Member, UpdateMemberPayload } from "@/lib/types/members"

export function useMemberMutations(orgId: string) {
  const queryClient = useQueryClient()

  const jsonHeaders = {
    "Content-Type": "application/json",
    ...getCsrfHeader(),
  }

  function invalidateMembers() {
    queryClient.invalidateQueries({ queryKey: ["members", orgId] })
  }

  const addMember = useMutation({
    mutationFn: (payload: AddMemberPayload) =>
      apiRequest<Member>(`orgs/${orgId}/members/`, {
        method: "POST",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
      }),
    onSuccess: invalidateMembers,
  })

  const updateMember = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: UpdateMemberPayload }) =>
      apiRequest<Member>(`orgs/${orgId}/members/${id}/`, {
        method: "PATCH",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
      }),
    onSuccess: invalidateMembers,
  })

  const deactivateMember = useMutation({
    mutationFn: (id: number) =>
      apiRequest<void>(`orgs/${orgId}/members/${id}/`, {
        method: "DELETE",
        headers: getCsrfHeader(),
      }),
    onSuccess: invalidateMembers,
  })

  return {
    addMember,
    updateMember,
    deactivateMember,
  }
}
