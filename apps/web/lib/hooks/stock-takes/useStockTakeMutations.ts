"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { getCsrfHeader } from "@/lib/csrf"
import type {
  CreateStockTakePayload,
  StockTakeDetail,
  StockTakeLine,
  UpdateStockTakeLinePayload,
  UpdateStockTakeNotesPayload,
} from "@/lib/types/stock-takes"

export function useStockTakeMutations(orgId: string) {
  const queryClient = useQueryClient()
  const headers = { "Content-Type": "application/json", ...getCsrfHeader() }

  const createStockTake = useMutation({
    mutationFn: (payload: CreateStockTakePayload) =>
      apiRequest<StockTakeDetail>(`orgs/${orgId}/stock-takes/`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stock-takes", orgId] })
    },
  })

  const updateStockTakeNotes = useMutation({
    mutationFn: ({
      stockTakeId,
      payload,
    }: {
      stockTakeId: string
      payload: UpdateStockTakeNotesPayload
    }) =>
      apiRequest<StockTakeDetail>(`orgs/${orgId}/stock-takes/${stockTakeId}/`, {
        method: "PATCH",
        headers,
        body: JSON.stringify(payload),
      }),
    onSuccess: (_, { stockTakeId }) => {
      queryClient.invalidateQueries({
        queryKey: ["stock-takes", orgId, "detail", stockTakeId],
      })
    },
  })

  const updateStockTakeLine = useMutation({
    mutationFn: ({
      stockTakeId,
      lineId,
      payload,
    }: {
      stockTakeId: string
      lineId: number
      payload: UpdateStockTakeLinePayload
    }) =>
      apiRequest<StockTakeLine>(`orgs/${orgId}/stock-takes/${stockTakeId}/lines/${lineId}/`, {
        method: "PATCH",
        headers,
        body: JSON.stringify(payload),
      }),
    onSuccess: (_, { stockTakeId }) => {
      queryClient.invalidateQueries({
        queryKey: ["stock-takes", orgId, "detail", stockTakeId],
      })
    },
  })

  const stockTakeAction = useMutation({
    mutationFn: ({
      stockTakeId,
      action,
    }: {
      stockTakeId: string
      action: "start" | "submit" | "approve" | "reopen" | "cancel"
    }) =>
      apiRequest<StockTakeDetail>(`orgs/${orgId}/stock-takes/${stockTakeId}/${action}/`, {
        method: "POST",
        headers: getCsrfHeader(),
      }),
    onSuccess: (_, { stockTakeId }) => {
      queryClient.invalidateQueries({ queryKey: ["stock-takes", orgId] })
      queryClient.invalidateQueries({
        queryKey: ["stock-takes", orgId, "detail", stockTakeId],
      })
    },
  })

  return {
    createStockTake,
    updateStockTakeNotes,
    updateStockTakeLine,
    stockTakeAction,
  }
}
