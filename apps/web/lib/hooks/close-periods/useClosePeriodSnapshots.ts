"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { CloseSnapshot } from "@/lib/types/close-periods"

interface UseClosePeriodSnapshotsParams {
  orgId: string
  periodId: string
}

export function useClosePeriodSnapshots({ orgId, periodId }: UseClosePeriodSnapshotsParams) {
  return useQuery({
    queryKey: ["close-period-snapshots", orgId, periodId],
    queryFn: () =>
      apiRequest<CloseSnapshot[]>(`orgs/${orgId}/close-periods/${periodId}/snapshots/`),
    enabled: !!orgId && !!periodId,
  })
}
