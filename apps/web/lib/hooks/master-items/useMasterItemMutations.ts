"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { getCsrfHeader } from "@/lib/csrf"
import type {
  CreateMasterItemPayload,
  MasterItem,
  UpdateMasterItemPayload,
} from "@/lib/types/master-items"

export function useMasterItemMutations() {
  const queryClient = useQueryClient()

  const jsonHeaders = {
    "Content-Type": "application/json",
    ...getCsrfHeader(),
  }

  const createMasterItem = useMutation({
    mutationFn: (payload: CreateMasterItemPayload) =>
      apiRequest<MasterItem>("parent/master-items/", {
        method: "POST",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["master-items"] })
    },
  })

  const updateMasterItem = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateMasterItemPayload }) =>
      apiRequest<MasterItem>(`parent/master-items/${id}/`, {
        method: "PATCH",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
      }),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["master-items"] })
      queryClient.invalidateQueries({ queryKey: ["master-items", "detail", id] })
    },
  })

  const deactivateMasterItem = useMutation({
    mutationFn: (id: string) =>
      apiRequest<void>(`parent/master-items/${id}/`, {
        method: "DELETE",
        headers: getCsrfHeader(),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["master-items"] })
    },
  })

  return {
    createMasterItem,
    updateMasterItem,
    deactivateMasterItem,
  }
}
