"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { ClosePeriod } from "@/lib/types/close-periods"

interface UseClosePeriodsParams {
  orgId: string
}

export function useClosePeriods({ orgId }: UseClosePeriodsParams) {
  return useQuery({
    queryKey: ["close-periods", orgId],
    queryFn: () => apiRequest<ClosePeriod[]>(`orgs/${orgId}/close-periods/`),
    enabled: !!orgId,
  })
}
