"use client"

import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export interface POReceiptLineRow {
  po_line: string
  item: string
  ordered_quantity: number
  remaining_quantity: number
  quantity_received: number
  unit_cost: string
}

interface POReceiptLineTableProps {
  lines: POReceiptLineRow[]
  onChange: (lines: POReceiptLineRow[]) => void
}

function truncateUuid(value: string) {
  return `${value.slice(0, 8)}...`
}

export function POReceiptLineTable({ lines, onChange }: POReceiptLineTableProps) {
  if (lines.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
        All lines on this PO have been fully received
      </div>
    )
  }

  function updateLine(index: number, patch: Partial<POReceiptLineRow>) {
    onChange(lines.map((line, currentIndex) => (currentIndex === index ? { ...line, ...patch } : line)))
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Item</TableHead>
          <TableHead>Ordered</TableHead>
          <TableHead>Remaining</TableHead>
          <TableHead>Qty to Receive</TableHead>
          <TableHead>Unit Cost</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {lines.map((line, index) => {
          const invalidQuantity =
            line.quantity_received <= 0 || line.quantity_received > line.remaining_quantity

          return (
            <TableRow key={line.po_line}>
              <TableCell className="font-mono text-sm">{truncateUuid(line.item)}</TableCell>
              <TableCell>{line.ordered_quantity}</TableCell>
              <TableCell>{line.remaining_quantity}</TableCell>
              <TableCell className="space-y-2">
                <Input
                  type="number"
                  min="1"
                  max={String(line.remaining_quantity)}
                  step="1"
                  value={String(line.quantity_received)}
                  onChange={(event) =>
                    updateLine(index, {
                      quantity_received: Number.parseInt(event.target.value, 10) || 0,
                    })
                  }
                />
                {invalidQuantity ? (
                  <p className="text-xs text-red-600">
                    Quantity must be greater than 0 and no more than remaining quantity.
                  </p>
                ) : null}
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={line.unit_cost}
                  onChange={(event) => updateLine(index, { unit_cost: event.target.value })}
                />
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
