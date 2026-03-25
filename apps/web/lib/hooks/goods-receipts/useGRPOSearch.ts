"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"

export interface GRPOSearchLine {
  id: string
  item: {
    id: string
    name: string
    sku: string
  }
  ordered_quantity: number
  unit_price: string
  received_quantity: number
}

export interface GRPOSearchResult {
  id: string
  po_number: string
  supplier: string
  branch: string
  status: string
  lines: GRPOSearchLine[]
}

interface GRPOSearchResponse {
  results: GRPOSearchResult[]
  next: string | null
}

export function useGRPOSearch(orgId: string, query: string) {
  const enabled = !!orgId && query.trim().length >= 2

  return useQuery<GRPOSearchResponse>({
    queryKey: ["gr-po-search", orgId, query],
    queryFn: () => {
      const params = new URLSearchParams({
        search: query,
        status: "SUBMITTED,PARTIALLY_RECEIVED",
      })

      return apiRequest<GRPOSearchResponse>(`orgs/${orgId}/purchase-orders/?${params.toString()}`)
    },
    enabled,
  })
}
