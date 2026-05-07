"use client"

import { useCallback, useState } from "react"

import { BarcodeScanner } from "@/components/scanner/BarcodeScanner"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { useScanResolver } from "@/lib/hooks/scan/useScanResolver"
import type { ScanStatus } from "@/lib/types/scan"

interface CountLine {
  lineId: number
  orgItemId: string
  name: string
  sku: string
  snapshot: string
  counted: number
}

interface CountScanModeProps {
  orgId: string
  branchId: string
  stockTakeId: string
  onBulkUpdate: (lines: { id: number; counted_quantity: string }[]) => Promise<void>
  isPending: boolean
}

function outcomeMessage(outcome: string): string {
  switch (outcome) {
    case "not_found":
      return "Item not found."
    case "not_enabled_at_branch":
      return "Item not enabled at this branch."
    case "not_in_count":
      return "Item is not included in this stock take."
    case "ambiguous":
      return "Multiple items matched — check SKU."
    default:
      return "Scan error."
  }
}

export function CountScanMode({
  orgId,
  branchId,
  stockTakeId,
  onBulkUpdate,
  isPending,
}: CountScanModeProps) {
  const [lines, setLines] = useState<CountLine[]>([])
  const [scanStatus, setScanStatus] = useState<ScanStatus>("idle")
  const [scanMessage, setScanMessage] = useState("")
  const { resolve } = useScanResolver({ orgId, branchId, stockTakeId })

  const handleScan = useCallback(
    async (code: string) => {
      setScanStatus("captured")
      setScanMessage("")
      const result = await resolve(code)
      if (!result) {
        setScanStatus("failed")
        setScanMessage("Scan resolution failed.")
        return
      }
      if (result.outcome !== "matched" || !result.item) {
        setScanStatus("failed")
        setScanMessage(outcomeMessage(result.outcome))
        return
      }

      const item = result.item
      if (!item.stock_take_line_id) {
        setScanStatus("failed")
        setScanMessage("Item matched but has no stock take line.")
        return
      }

      setScanStatus("resolved")
      setLines((prev) => {
        const existing = prev.find((l) => l.orgItemId === item.org_item_id)
        if (existing) {
          return prev.map((l) =>
            l.orgItemId === item.org_item_id ? { ...l, counted: l.counted + 1 } : l,
          )
        }
        const currentCounted = item.counted_quantity != null ? Number(item.counted_quantity) : 0
        return [
          ...prev,
          {
            lineId: item.stock_take_line_id!,
            orgItemId: item.org_item_id,
            name: item.name,
            sku: item.sku,
            snapshot: item.snapshot_quantity ?? "0",
            counted: currentCounted + 1,
          },
        ]
      })
    },
    [resolve],
  )

  const updateCounted = useCallback((orgItemId: string, qty: number) => {
    setLines((prev) =>
      prev.map((l) =>
        l.orgItemId === orgItemId ? { ...l, counted: Math.max(0, qty) } : l,
      ),
    )
  }, [])

  const handleSave = useCallback(async () => {
    if (lines.length === 0) return
    await onBulkUpdate(
      lines.map((l) => ({ id: l.lineId, counted_quantity: String(l.counted) })),
    )
    setLines([])
    setScanStatus("idle")
  }, [lines, onBulkUpdate])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Scan Items to Count</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <BarcodeScanner onScan={handleScan} disabled={isPending} />
          {scanStatus === "failed" && scanMessage && (
            <p className="text-sm text-red-600">{scanMessage}</p>
          )}
          {scanStatus === "resolved" && (
            <p className="text-sm text-green-600">Count updated.</p>
          )}
        </CardContent>
      </Card>

      {lines.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Scanned Counts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {lines.map((line) => (
                <div key={line.orgItemId} className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{line.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {line.sku} · snapshot: {line.snapshot}
                    </p>
                  </div>
                  <Input
                    type="number"
                    min={0}
                    value={line.counted}
                    onChange={(e) => updateCounted(line.orgItemId, parseInt(e.target.value, 10) || 0)}
                    disabled={isPending}
                    className="w-24 text-center"
                  />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex justify-end">
        <Button
          onClick={() => void handleSave()}
          disabled={isPending || lines.length === 0}
        >
          {isPending ? "Saving…" : `Save ${lines.length} Count${lines.length !== 1 ? "s" : ""}`}
        </Button>
      </div>
    </div>
  )
}
