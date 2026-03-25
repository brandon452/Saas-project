"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { useAuth } from "@/lib/hooks/useAuth"
import type { MasterItemListResponse } from "@/lib/types/master-items"

interface UseMasterItemsParams {
  search?: string
  is_active: "true" | "false"
  page?: string
}

export function useMasterItems(params: UseMasterItemsParams) {
  const { user } = useAuth()

  return useQuery<MasterItemListResponse>({
    queryKey: ["master-items", params.search, params.is_active, params.page],
    queryFn: async () => {
      const searchParams = new URLSearchParams()

      if (params.search) searchParams.set("search", params.search)
      searchParams.set("is_active", params.is_active)
      if (params.page) searchParams.set("page", params.page)

      const query = searchParams.toString()
      return apiRequest<MasterItemListResponse>(`parent/master-items/${query ? `?${query}` : ""}`)
    },
    enabled: !!user?.is_parent_member,
  })
}
