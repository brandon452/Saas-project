"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { OrgSettings, UpdateOrgSettingsPayload } from "@/lib/types/org-settings"

export function useOrgSettings(orgId: string) {
  return useQuery<OrgSettings>({
    queryKey: ["org-settings", orgId],
    queryFn: () => apiRequest<OrgSettings>(`orgs/${orgId}/settings/`),
    enabled: !!orgId,
    retry: false,
  })
}

export function useOrgSettingsMutation(orgId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: UpdateOrgSettingsPayload) =>
      apiRequest<OrgSettings>(`orgs/${orgId}/settings/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: async (settings) => {
      queryClient.setQueryData(["org-settings", orgId], settings)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["orgs", "accessible"] }),
        queryClient.invalidateQueries({ queryKey: ["auth", "me"] }),
      ])
    },
  })
}
