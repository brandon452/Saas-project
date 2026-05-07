"use client"

import { useCallback, useState } from "react"
import { Trash2 } from "lucide-react"

import { BarcodeScanner } from "@/components/scanner/BarcodeScanner"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useScanResolver } from "@/lib/hooks/scan/useScanResolver"
import type { DirectReceiptLineInput } from "@/lib/types/goods-receipts"
import type { ScanStatus } from "@/lib/types/scan"

export interface ReceiveScanLine {
  orgItemId: string
  name: string
  sku: string
  quantity: number
  unitCost: string
}

interface ReceiveScanModeProps {
  orgId: string
  branchId: string
  onSubmitLines: (lines: DirectReceiptLineInput[]) => Promise<void>
  isPending: boolean
}

function outcomeMessage(outcome: string): string {
  switch (outcome) {
    case "not_found":
      return "Item not found."
    case "not_enabled_at_branch":
      return "Item not enabled at this branch."
    case "ambiguous":
      return "Multiple items matched — check SKU."
    default:
      return "Scan error."
  }
}

export function ReceiveScanMode({ orgId, branchId, onSubmitLines, isPending }: ReceiveScanModeProps) {
  const [lines, setLines] = useState<ReceiveScanLine[]>([])
  const [scanStatus, setScanStatus] = useState<ScanStatus>("idle")
  const [scanMessage, setScanMessage] = useState("")
  const [submitError, setSubmitError] = useState("")
  const { resolve } = useScanResolver({ orgId, branchId })

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
      setScanStatus("resolved")
      setLines((prev) => {
        const existing = prev.find((l) => l.orgItemId === result.item!.org_item_id)
        if (existing) {
          return prev.map((l) =>
            l.orgItemId === result.item!.org_item_id
              ? { ...l, quantity: l.quantity + 1 }
              : l,
          )
        }
        return [
          ...prev,
          {
            orgItemId: result.item!.org_item_id,
            name: result.item!.name,
            sku: result.item!.sku,
            quantity: 1,
            unitCost: "",
          },
        ]
      })
    },
    [resolve],
  )

  const updateQty = useCallback((orgItemId: string, qty: number) => {
    setLines((prev) =>
      prev.map((l) => (l.orgItemId === orgItemId ? { ...l, quantity: Math.max(1, qty) } : l)),
    )
  }, [])

  const updateCost = useCallback((orgItemId: string, cost: string) => {
    setLines((prev) =>
      prev.map((l) => (l.orgItemId === orgItemId ? { ...l, unitCost: cost } : l)),
    )
  }, [])

  const removeLine = useCallback((orgItemId: string) => {
    setLines((prev) => prev.filter((l) => l.orgItemId !== orgItemId))
  }, [])

  const handleSubmit = useCallback(async () => {
    setSubmitError("")
    if (lines.length === 0) {
      setSubmitError("Scan at least one item.")
      return
    }
    for (const line of lines) {
      const cost = Number(line.unitCost)
      if (!line.unitCost || isNaN(cost) || cost < 0) {
        setSubmitError(`Enter a valid unit cost for "${line.name}".`)
        return
      }
    }
    await onSubmitLines(
      lines.map((l) => ({
        item: l.orgItemId,
        quantity_received: l.quantity,
        unit_cost: l.unitCost,
      })),
    )
    setLines([])
    setScanStatus("idle")
  }, [lines, onSubmitLines])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Scan Items to Receive</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <BarcodeScanner onScan={handleScan} disabled={isPending} />
          {scanStatus === "failed" && scanMessage && (
            <p className="text-sm text-red-600">{scanMessage}</p>
          )}
          {scanStatus === "resolved" && (
            <p className="text-sm text-green-600">Item added to receipt.</p>
          )}
        </CardContent>
      </Card>

      {lines.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Receipt Lines</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {lines.map((line) => (
              <div key={line.orgItemId} className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{line.name}</p>
                  <p className="text-xs text-muted-foreground">{line.sku}</p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-20">
                    <Label className="sr-only">Qty</Label>
                    <Input
                      type="number"
                      min={1}
                      value={line.quantity}
                      onChange={(e) => updateQty(line.orgItemId, parseInt(e.target.value, 10))}
                      disabled={isPending}
                      className="text-center"
                    />
                  </div>
                  <div className="w-28">
                    <Label className="sr-only">Unit cost</Label>
                    <Input
                      type="number"
                      min={0}
                      step="0.01"
                      placeholder="Unit cost*"
                      value={line.unitCost}
                      onChange={(e) => updateCost(line.orgItemId, e.target.value)}
                      disabled={isPending}
                    />
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => removeLine(line.orgItemId)}
                    disabled={isPending}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
            <p className="text-xs text-muted-foreground">* Unit cost is required for direct receipts.</p>
          </CardContent>
        </Card>
      )}

      {submitError && <p className="text-sm text-red-600">{submitError}</p>}

      <div className="flex justify-end">
        <Button
          onClick={() => void handleSubmit()}
          disabled={isPending || lines.length === 0}
        >
          {isPending ? "Receiving…" : "Post Receipt"}
        </Button>
      </div>
    </div>
  )
}
