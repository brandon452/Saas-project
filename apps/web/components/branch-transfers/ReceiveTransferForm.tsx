"use client"

import { useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type {
  BranchTransfer,
  BranchTransferItem,
  ReceiveTransferPayload,
} from "@/lib/types/branch-transfers"

interface ReceiveTransferFormProps {
  transfer: BranchTransfer
  onSubmit: (payload: ReceiveTransferPayload) => void
  onCancel: () => void
  isPending: boolean
}

interface ReceiveLineDraft {
  line_id: number
  item: BranchTransferItem
  quantity_sent: number
  quantity_received: number
}

export function ReceiveTransferForm({
  transfer,
  onSubmit,
  onCancel,
  isPending,
}: ReceiveTransferFormProps) {
  const [lines, setLines] = useState<ReceiveLineDraft[]>(
    transfer.lines.map((line) => ({
      line_id: line.id,
      item: line.item,
      quantity_sent: line.quantity_sent,
      quantity_received: line.quantity_sent,
    })),
  )
  const [notes, setNotes] = useState("")

  const hasAnyReceived = useMemo(
    () => lines.some((line) => line.quantity_received > 0),
    [lines],
  )
  const hasInvalidLines = useMemo(
    () =>
      lines.some(
        (line) =>
          line.quantity_received < 0 || line.quantity_received > line.quantity_sent,
      ),
    [lines],
  )

  function updateLine(lineId: number, quantityReceived: number) {
    setLines((current) =>
      current.map((line) =>
        line.line_id === lineId
          ? { ...line, quantity_received: quantityReceived }
          : line,
      ),
    )
  }

  function handleSubmit() {
    if (hasInvalidLines || !hasAnyReceived) return

    onSubmit({
      lines: lines.map((line) => ({
        line_id: line.line_id,
        quantity_received: line.quantity_received,
      })),
      notes,
    })
  }

  return (
    <div className="space-y-4 rounded-xl border border-border p-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Item</TableHead>
            <TableHead>Qty Sent</TableHead>
            <TableHead>Qty Received</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {lines.map((line) => {
            const invalid =
              line.quantity_received < 0 ||
              line.quantity_received > line.quantity_sent

            return (
              <TableRow key={line.line_id}>
                <TableCell>{line.item.name}</TableCell>
                <TableCell>{line.quantity_sent}</TableCell>
                <TableCell className="space-y-2">
                  <Input
                    type="number"
                    min="0"
                    max={String(line.quantity_sent)}
                    step="1"
                    value={String(line.quantity_received)}
                    onChange={(event) =>
                      updateLine(
                        line.line_id,
                        Number.parseInt(event.target.value, 10) || 0,
                      )
                    }
                    disabled={isPending}
                  />
                  {invalid ? (
                    <p className="text-xs text-red-600">
                      Quantity must be between 0 and qty sent.
                    </p>
                  ) : null}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>

      <div className="space-y-2">
        <Label htmlFor="receive-notes">Receive notes</Label>
        <Textarea
          id="receive-notes"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          disabled={isPending}
        />
      </div>

      {!hasAnyReceived ? (
        <p className="text-sm text-red-600">At least one line must have quantity received greater than 0.</p>
      ) : null}

      <div className="flex items-center justify-end gap-3">
        <Button variant="outline" onClick={onCancel} disabled={isPending}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={isPending || hasInvalidLines || !hasAnyReceived}>
          {isPending ? "Receiving..." : "Confirm Receipt"}
        </Button>
      </div>
    </div>
  )
}
