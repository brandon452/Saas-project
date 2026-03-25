"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { useAuth } from "@/lib/hooks/useAuth"
import type { MasterItem } from "@/lib/types/master-items"

export function useMasterItemDetail(id: string | null) {
  const { user } = useAuth()

  return useQuery<MasterItem>({
    queryKey: ["master-items", "detail", id],
    queryFn: () => apiRequest<MasterItem>(`parent/master-items/${id}/`),
    enabled: !!user?.is_parent_member && !!id,
  })
}
