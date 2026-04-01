"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { ClosePeriod } from "@/lib/types/close-periods"

interface CreatePeriodPayload {
  start_date: string
  end_date: string
  notes: string
}

export function useClosePeriodMutations(orgId: string) {
  const queryClient = useQueryClient()

  function invalidatePeriods() {
    void queryClient.invalidateQueries({ queryKey: ["close-periods", orgId] })
  }

  function invalidateValuation() {
    void queryClient.invalidateQueries({ queryKey: ["stock-valuation", orgId] })
  }

  const createPeriod = useMutation({
    mutationFn: (payload: CreatePeriodPayload) =>
      apiRequest<ClosePeriod>(`orgs/${orgId}/close-periods/`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: invalidatePeriods,
  })

  const closePeriod = useMutation({
    mutationFn: (id: string) =>
      apiRequest<ClosePeriod>(`orgs/${orgId}/close-periods/${id}/close/`, {
        method: "POST",
      }),
    onSuccess: () => {
      invalidatePeriods()
      invalidateValuation()
    },
  })

  const reopenPeriod = useMutation({
    mutationFn: (id: string) =>
      apiRequest<ClosePeriod>(`orgs/${orgId}/close-periods/${id}/reopen/`, {
        method: "POST",
      }),
    onSuccess: () => {
      invalidatePeriods()
      invalidateValuation()
    },
  })

  return { createPeriod, closePeriod, reopenPeriod }
}
