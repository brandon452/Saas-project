"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"

export interface OrgOption {
  id: string
  name: string
  slug: string
}

export function useAccessibleOrgs(enabled: boolean = true) {
  return useQuery<OrgOption[]>({
    queryKey: ["orgs", "accessible"],
    queryFn: () => apiRequest<OrgOption[]>("orgs/"),
    enabled,
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
}
