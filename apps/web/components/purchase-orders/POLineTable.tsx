"use client"

import { useEffect, useState } from "react"

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
import type { POLine } from "@/lib/types/purchase-orders"
import { formatPOValue } from "@/lib/utils/po"

interface POLineTableProps {
  lines: POLine[]
  editable?: boolean
  busy?: boolean
  onUpdateLine?: (
    lineId: number,
    data: Partial<{ ordered_quantity: number; unit_price: string }>,
  ) => Promise<void>
  onRemoveLine?: (lineId: number) => Promise<void>
}

type DraftValues = Record<number, { ordered_quantity: string; unit_price: string }>

export function POLineTable({
  lines,
  editable,
  busy,
  onUpdateLine,
  onRemoveLine,
}: POLineTableProps) {
  const [draftValues, setDraftValues] = useState<DraftValues>({})
  const [rowError, setRowError] = useState<string>("")

  useEffect(() => {
    const nextDrafts: DraftValues = {}
    for (const line of lines) {
      nextDrafts[line.id] = {
        ordered_quantity: String(line.ordered_quantity),
        unit_price: line.unit_price,
      }
    }
    setDraftValues(nextDrafts)
    setRowError("")
  }, [lines])

  async function handleBlur(line: POLine, field: "ordered_quantity" | "unit_price") {
    if (!editable || !onUpdateLine) return

    const draft = draftValues[line.id]
    if (!draft) return

    const originalValue = field === "ordered_quantity" ? String(line.ordered_quantity) : line.unit_price
    const nextValue = draft[field].trim()

    if (nextValue === originalValue) return

    const invalidNumber =
      field === "ordered_quantity"
        ? !Number.isInteger(Number.parseInt(nextValue, 10)) || Number.parseInt(nextValue, 10) <= 0
        : !Number.isFinite(Number.parseFloat(nextValue)) || Number.parseFloat(nextValue) <= 0

    if (invalidNumber) {
      setRowError("Line values must be greater than zero.")
      setDraftValues((current) => ({
        ...current,
        [line.id]: {
          ordered_quantity: String(line.ordered_quantity),
          unit_price: line.unit_price,
        },
      }))
      return
    }

    try {
      setRowError("")
      await onUpdateLine(
        line.id,
        field === "ordered_quantity"
          ? { ordered_quantity: Number.parseInt(nextValue, 10) }
          : { unit_price: Number.parseFloat(nextValue).toFixed(2) },
      )
    } catch {
      setRowError("Failed to save line changes.")
      setDraftValues((current) => ({
        ...current,
        [line.id]: {
          ordered_quantity: String(line.ordered_quantity),
          unit_price: line.unit_price,
        },
      }))
    }
  }

  return (
    <div className="space-y-3">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Item</TableHead>
            <TableHead>Ordered Qty</TableHead>
            <TableHead>Unit Price</TableHead>
            <TableHead>Line Total</TableHead>
            <TableHead>Received Qty</TableHead>
            {editable ? <TableHead className="w-24">Actions</TableHead> : null}
          </TableRow>
        </TableHeader>
        <TableBody>
          {lines.map((line) => {
            const draft = draftValues[line.id]
            const quantity = Number.parseInt(draft?.ordered_quantity ?? String(line.ordered_quantity), 10) || 0
            const price = Number.parseFloat(draft?.unit_price ?? line.unit_price) || 0

            return (
              <TableRow key={line.id}>
                <TableCell>{line.item.name}</TableCell>
                <TableCell>
                  {editable ? (
                    <Input
                      value={draft?.ordered_quantity ?? String(line.ordered_quantity)}
                      onChange={(event) =>
                        setDraftValues((current) => ({
                          ...current,
                          [line.id]: {
                            ordered_quantity: event.target.value,
                            unit_price: current[line.id]?.unit_price ?? line.unit_price,
                          },
                        }))
                      }
                      onBlur={() => void handleBlur(line, "ordered_quantity")}
                      disabled={busy}
                      type="number"
                      min="1"
                      step="1"
                    />
                  ) : (
                    line.ordered_quantity
                  )}
                </TableCell>
                <TableCell>
                  {editable ? (
                    <Input
                      value={draft?.unit_price ?? line.unit_price}
                      onChange={(event) =>
                        setDraftValues((current) => ({
                          ...current,
                          [line.id]: {
                            ordered_quantity:
                              current[line.id]?.ordered_quantity ?? String(line.ordered_quantity),
                            unit_price: event.target.value,
                          },
                        }))
                      }
                      onBlur={() => void handleBlur(line, "unit_price")}
                      disabled={busy}
                      type="number"
                      min="0.01"
                      step="0.01"
                    />
                  ) : (
                    formatPOValue(parseFloat(line.unit_price))
                  )}
                </TableCell>
                <TableCell>{formatPOValue(quantity * price)}</TableCell>
                <TableCell>{line.received_quantity ?? "—"}</TableCell>
                {editable ? (
                  <TableCell>
                    <Button
                      variant="ghost"
                      className="text-red-600 hover:text-red-700"
                      disabled={busy}
                      onClick={() => void onRemoveLine?.(line.id)}
                    >
                      Remove
                    </Button>
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
