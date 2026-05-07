"use client"

import { useCallback, useState } from "react"
import { CheckCircle, Circle } from "lucide-react"

import { BarcodeScanner } from "@/components/scanner/BarcodeScanner"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useScanResolver } from "@/lib/hooks/scan/useScanResolver"
import type { BranchTransferLine } from "@/lib/types/branch-transfers"
import type { ScanStatus } from "@/lib/types/scan"

interface TransferDispatchVerifyModeProps {
  orgId: string
  branchId: string
  lines: BranchTransferLine[]
  onDispatch: () => Promise<void>
  isPending: boolean
}

export function TransferDispatchVerifyMode({
  orgId,
  branchId,
  lines,
  onDispatch,
  isPending,
}: TransferDispatchVerifyModeProps) {
  const [verifiedIds, setVerifiedIds] = useState<Set<string>>(new Set())
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
      setScanMessage(`Verified: ${result.item.name}`)
      setVerifiedIds((prev) => new Set(prev).add(matched.item.id))
    },
    [resolve, lines],
  )

  const allVerified = lines.every((l) => verifiedIds.has(l.item.id))

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Verify Items Before Dispatch</CardTitle>
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
          <CardTitle className="text-base">Transfer Lines</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {lines.map((line) => (
              <li key={line.id} className="flex items-center gap-3">
                {verifiedIds.has(line.item.id) ? (
                  <CheckCircle className="h-5 w-5 text-green-600 shrink-0" />
                ) : (
                  <Circle className="h-5 w-5 text-muted-foreground shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{line.item.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {line.item.sku} · qty: {line.quantity_sent}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-3">
        {!allVerified && (
          <p className="text-sm text-muted-foreground self-center">
            {verifiedIds.size}/{lines.length} verified
          </p>
        )}
        <Button onClick={() => void onDispatch()} disabled={isPending}>
          {isPending ? "Dispatching…" : "Dispatch"}
        </Button>
      </div>
    </div>
  )
}
