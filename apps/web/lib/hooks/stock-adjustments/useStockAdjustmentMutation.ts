"use client"

import { useMutation } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { PostAdjustmentPayload, StockLedgerEntry } from "@/lib/types/stock-adjustments"

export function useStockAdjustmentMutation(orgId: string, branchId: string) {
  return useMutation({
    mutationFn: (payload: PostAdjustmentPayload) =>
      apiRequest<StockLedgerEntry>(
        `orgs/${orgId}/inventory/movements/`,
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
        undefined,
        branchId,
      ),
  })
}
