"use client"

import { useEffect, useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useStockTakeMutations } from "@/lib/hooks/stock-takes/useStockTakeMutations"
import type { StockTakeLine, StockTakeStatus } from "@/lib/types/stock-takes"
import { canEditLines, formatQuantity } from "@/lib/utils/stock-takes"

interface StockTakeLinesTableProps {
  orgId: string
  stockTakeId: string
  status: StockTakeStatus
  lines: StockTakeLine[]
  onSaved: () => Promise<void> | void
}

type DraftMap = Record<number, string>

export function StockTakeLinesTable({
  orgId,
  stockTakeId,
  status,
  lines,
  onSaved,
}: StockTakeLinesTableProps) {
  const { updateStockTakeLine } = useStockTakeMutations(orgId)
  const [drafts, setDrafts] = useState<DraftMap>({})
  const [rowError, setRowError] = useState("")
  const [activeLineId, setActiveLineId] = useState<number | null>(null)

  useEffect(() => {
    const nextDrafts: DraftMap = {}
    for (const line of lines) {
      nextDrafts[line.id] = line.counted_quantity ?? ""
    }
    setDrafts(nextDrafts)
    setRowError("")
  }, [lines])

  const editable = useMemo(() => canEditLines(status), [status])

  async function saveLine(line: StockTakeLine, nextValue: string) {
    if (!editable) return

    const trimmed = nextValue.trim()
    if (trimmed && Number(trimmed) < 0) {
      setRowError("Counted quantity cannot be negative.")
      return
    }

    try {
      setRowError("")
      setActiveLineId(line.id)
      await updateStockTakeLine.mutateAsync({
        stockTakeId,
        lineId: line.id,
        payload: {
          counted_quantity: trimmed === "" ? null : trimmed,
        },
      })
      await onSaved()
    } catch (error) {
      const message = error instanceof Error ? error.message : ""
      if (message.includes("403")) {
        setRowError("You do not have permission to update counted quantities.")
      } else if (message.includes("400")) {
        setRowError("Could not save counted quantity.")
      } else {
        setRowError(message || "Failed to save counted quantity.")
      }
    } finally {
      setActiveLineId(null)
    }
  }

  return (
    <div className="space-y-3">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Item</TableHead>
            <TableHead>SKU</TableHead>
            <TableHead>Snapshot Qty</TableHead>
            <TableHead>Counted Qty</TableHead>
            <TableHead>Variance</TableHead>
            {editable ? <TableHead className="w-44">Actions</TableHead> : null}
          </TableRow>
        </TableHeader>
        <TableBody>
          {lines.map((line) => {
            const lineBusy = updateStockTakeLine.isPending && activeLineId === line.id

            return (
              <TableRow key={line.id}>
                <TableCell className="font-medium">{line.item_name}</TableCell>
                <TableCell>{line.item_sku}</TableCell>
                <TableCell>{formatQuantity(line.snapshot_quantity)}</TableCell>
                <TableCell>
                  {editable ? (
                    <Input
                      value={drafts[line.id] ?? ""}
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [line.id]: event.target.value,
                        }))
                      }
                      disabled={lineBusy}
                      inputMode="decimal"
                      placeholder="Enter count"
                    />
                  ) : (
                    formatQuantity(line.counted_quantity)
                  )}
                </TableCell>
                <TableCell>{formatQuantity(line.variance_preview)}</TableCell>
                {editable ? (
                  <TableCell>
                    <div className="flex gap-2">
                      <Button
                        className="px-2 py-1 text-xs"
                        disabled={lineBusy}
                        onClick={() => void saveLine(line, drafts[line.id] ?? "")}
                      >
                        {lineBusy ? "Saving..." : "Save"}
                      </Button>
                      <Button
                        variant="ghost"
                        className="px-2 py-1 text-xs"
                        disabled={lineBusy}
                        onClick={() => void saveLine(line, "")}
                      >
                        Clear
                      </Button>
                    </div>
                  </TableCell>
                ) : null}
              </TableRow>
            )
          })}
        </TableBody>
      </Table>

      {rowError ? <p className="text-sm text-red-600">{rowError}</p> : null}
    </div>
  )
}
