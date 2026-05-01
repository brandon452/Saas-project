"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { ParentOrganization } from "@/lib/types/parent"

export interface CreateParentOrganizationPayload {
  name: string
  slug: string
  is_active?: boolean
}

export function useParentOrganizations() {
  return useQuery<ParentOrganization[]>({
    queryKey: ["parent", "organizations"],
    queryFn: () => apiRequest<ParentOrganization[]>("orgs/"),
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
}

export function useCreateParentOrganization() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CreateParentOrganizationPayload) =>
      apiRequest<ParentOrganization>("orgs/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["parent", "organizations"] })
      queryClient.invalidateQueries({ queryKey: ["orgs", "accessible"] })
    },
  })
}
