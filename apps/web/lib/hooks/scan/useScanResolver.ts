"use client"

import { useCallback, useState } from "react"

import { apiRequest } from "@/lib/api"
import type { ScanResolveResult, ScanStatus } from "@/lib/types/scan"
import { normalizeToken } from "@/lib/scan/scannerUtils"

interface UseScanResolverOptions {
  orgId: string
  branchId: string
  stockTakeId?: string
}

export function useScanResolver({ orgId, branchId, stockTakeId }: UseScanResolverOptions) {
  const [status, setStatus] = useState<ScanStatus>("idle")
  const [result, setResult] = useState<ScanResolveResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const resolve = useCallback(
    async (rawCode: string): Promise<ScanResolveResult | null> => {
      const code = normalizeToken(rawCode)
      if (!code) return null

      setStatus("captured")
      setError(null)

      const params = new URLSearchParams({ code, branch_id: branchId })
      if (stockTakeId) params.set("stock_take_id", stockTakeId)

      try {
        const data = await apiRequest<ScanResolveResult>(
          `orgs/${orgId}/inventory/items/resolve-scan/?${params.toString()}`,
        )
        setResult(data)
        setStatus("resolved")
        return data
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Scan resolution failed."
        setError(msg)
        setStatus("failed")
        return null
      }
    },
    [orgId, branchId, stockTakeId],
  )

  const reset = useCallback(() => {
    setStatus("idle")
    setResult(null)
    setError(null)
  }, [])

  return { resolve, reset, status, result, error }
}
