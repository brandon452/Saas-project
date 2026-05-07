"use client"

import { useCallback, useMemo, useState } from "react"

import { BarcodeScanner } from "@/components/scanner/BarcodeScanner"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { useScanResolver } from "@/lib/hooks/scan/useScanResolver"
import { generateIdempotencyKey } from "@/lib/scan/scannerUtils"
import type { BranchTransferLine, ReceiveTransferPayload } from "@/lib/types/branch-transfers"
import type { ScanStatus } from "@/lib/types/scan"

interface TransferReceiveScanModeProps {
  orgId: string
  branchId: string
  lines: BranchTransferLine[]
  onReceive: (payload: ReceiveTransferPayload) => Promise<void>
  isPending: boolean
}

export function TransferReceiveScanMode({
  orgId,
  branchId,
  lines,
  onReceive,
  isPending,
}: TransferReceiveScanModeProps) {
  const [receivedQtys, setReceivedQtys] = useState<Record<number, number>>(() =>
    Object.fromEntries(lines.map((l) => [l.id, l.quantity_sent])),
  )
  const [scanStatus, setScanStatus] = useState<ScanStatus>("idle")
  const [scanMessage, setScanMessage] = useState("")
  const { resolve } = useScanResolver({ orgId, branchId })

  const handleScan = useCallback(
    async (code: string) => {
      setScanStatus("captured")
      setScanMessage("")
      const result = await resolve(code)
      if (!result || result.outcome !== "matched" || !result.item) {
        setScanStatus("failed")
        setScanMessage(
          result?.outcome === "not_found"
            ? "Item not found."
            : result?.outcome === "not_enabled_at_branch"
              ? "Item not enabled at this branch."
              : "Scan failed.",
        )
        return
      }

      const matched = lines.find((l) => l.item.id === result.item!.org_item_id)
      if (!matched) {
        setScanStatus("failed")
        setScanMessage("Scanned item is not on this transfer.")
        return
      }

      setScanStatus("resolved")
      setScanMessage(`Confirmed: ${result.item.name}`)
    },
    [resolve, lines],
  )

  const updateQty = useCallback((lineId: number, qty: number) => {
    setReceivedQtys((prev) => ({ ...prev, [lineId]: Math.max(0, qty) }))
  }, [])

  const handleSubmit = useCallback(async () => {
    const payload: ReceiveTransferPayload = {
      lines: lines.map((l) => ({
        line_id: l.id,
        quantity_received: receivedQtys[l.id] ?? l.quantity_sent,
      })),
      notes: "",
      idempotency_key: generateIdempotencyKey(),
    }
    await onReceive(payload)
  }, [lines, receivedQtys, onReceive])

  const totalSent = useMemo(() => lines.reduce((s, l) => s + l.quantity_sent, 0), [lines])
  const totalReceiving = useMemo(
    () => Object.values(receivedQtys).reduce((s, q) => s + q, 0),
    [receivedQtys],
  )

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Scan to Confirm Items</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <BarcodeScanner onScan={handleScan} disabled={isPending} />
          {scanStatus === "failed" && scanMessage && (
            <p className="text-sm text-red-600">{scanMessage}</p>
          )}
          {scanStatus === "resolved" && scanMessage && (
            <p className="text-sm text-green-600">{scanMessage}</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Quantities to Receive</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {lines.map((line) => (
              <div key={line.id} className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{line.item.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {line.item.sku} · sent: {line.quantity_sent}
                  </p>
                </div>
                <Input
                  type="number"
                  min={0}
                  max={line.quantity_sent}
                  value={receivedQtys[line.id] ?? line.quantity_sent}
                  onChange={(e) => updateQty(line.id, parseInt(e.target.value, 10) || 0)}
                  disabled={isPending}
                  className="w-24 text-center"
                />
              </div>
            ))}
          </div>
          {totalReceiving < totalSent && (
            <p className="mt-3 text-sm text-amber-600">
              Variance: receiving {totalReceiving} of {totalSent} units.
            </p>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={() => void handleSubmit()} disabled={isPending}>
          {isPending ? "Receiving…" : "Confirm Receipt"}
        </Button>
      </div>
    </div>
  )
}
