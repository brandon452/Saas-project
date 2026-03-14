"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"

export interface GRItemSearchResult {
  id: string
  name: string
  sku: string
}

interface GRItemSearchResponse {
  results: GRItemSearchResult[]
  next: string | null
}

export function useGRItemSearch(orgId: string, query: string) {
  const enabled = !!orgId && query.trim().length >= 2

  return useQuery<GRItemSearchResponse>({
    queryKey: ["gr-item-search", orgId, query],
    queryFn: () => {
      const params = new URLSearchParams({ search: query })

      return apiRequest<GRItemSearchResponse>(`orgs/${orgId}/inventory/items/?${params.toString()}`)
    },
    enabled,
  })
}
