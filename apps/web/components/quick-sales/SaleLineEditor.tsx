"use client"

import { useQuery } from "@tanstack/react-query"
import { useEffect, useMemo } from "react"

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
import { apiRequest } from "@/lib/api"
import type { OrgItem } from "@/lib/types/org-items"
import { fetchAllPages } from "@/lib/utils/pagination"

export interface SaleLineDraft {
  itemId: string
  quantity: string
  unitPrice: string
}

interface SaleLineEditorProps {
  orgId: string
  branchId: string
  lines: SaleLineDraft[]
  onChange: (lines: SaleLineDraft[]) => void
  disabled?: boolean
}

function formatLineTotal(quantity: string, unitPrice: string) {
  const qty = Number.parseFloat(quantity)
  const price = Number.parseFloat(unitPrice)
  if (!Number.isFinite(qty) || !Number.isFinite(price)) return "0.00"
  return (qty * price).toFixed(2)
}

export function SaleLineEditor({
  orgId,
  branchId,
  lines,
  onChange,
  disabled,
}: SaleLineEditorProps) {
  const itemsQuery = useQuery<OrgItem[]>({
    queryKey: ["quick-sale-items", orgId, branchId],
    queryFn: () =>
      fetchAllPages<OrgItem>(
        `orgs/${orgId}/inventory/items/?is_active=true`,
        (path) => apiRequest(path, undefined, undefined, branchId),
      ),
    enabled: !!orgId && !!branchId,
  })

  useEffect(() => {
    if (branchId) return
    if (lines.length === 0) return
    onChange([])
  }, [branchId, lines.length, onChange])

  const availableItems = useMemo(() => itemsQuery.data ?? [], [itemsQuery.data])
  const itemMap = useMemo(
    () => new Map(availableItems.map((item) => [item.id, item])),
    [availableItems],
  )

  function updateLine(index: number, patch: Partial<SaleLineDraft>) {
    onChange(lines.map((line, currentIndex) => (currentIndex === index ? { ...line, ...patch } : line)))
  }

  function removeLine(index: number) {
    onChange(lines.filter((_, currentIndex) => currentIndex !== index))
  }

  function addLine() {
    onChange([...lines, { itemId: "", quantity: "", unitPrice: "" }])
  }

  const selectedItemIds = new Set(lines.map((line) => line.itemId).filter(Boolean))

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Item</TableHead>
              <TableHead>Quantity</TableHead>
              <TableHead>Unit Price</TableHead>
              <TableHead>Line Total</TableHead>
              <TableHead className="w-24">Remove</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {lines.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-sm text-muted-foreground">
                  Add at least one line to record this sale.
                </TableCell>
              </TableRow>
            ) : (
              lines.map((line, index) => {
                const quantity = Number.parseFloat(line.quantity)
                const unitPrice = Number.parseFloat(line.unitPrice)
                const invalidQuantity = !line.quantity.trim() || !Number.isFinite(quantity) || quantity <= 0
                const invalidUnitPrice = !line.unitPrice.trim() || !Number.isFinite(unitPrice) || unitPrice < 0

                return (
                  <TableRow key={`${line.itemId || "line"}-${index}`}>
                    <TableCell className="space-y-2">
                      <select
                        value={line.itemId}
                        onChange={(event) => updateLine(index, { itemId: event.target.value })}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
                        disabled={disabled || !branchId}
                      >
                        <option value="">Select item</option>
                        {availableItems
                          .filter((item) => item.id === line.itemId || !selectedItemIds.has(item.id))
                          .map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.name} ({item.sku})
                            </option>
                          ))}
                      </select>
                      {line.itemId && itemMap.get(line.itemId) ? (
                        <p className="text-xs text-muted-foreground">
                          SKU: {itemMap.get(line.itemId)?.sku}
                        </p>
                      ) : null}
                    </TableCell>
                    <TableCell className="space-y-2">
                      <Input
                        type="number"
                        min="0.0001"
                        step="0.0001"
                        value={line.quantity}
                        onChange={(event) => updateLine(index, { quantity: event.target.value })}
                        disabled={disabled || !branchId}
                      />
                      {invalidQuantity ? (
                        <p className="text-xs text-red-600">Quantity must be greater than 0.</p>
                      ) : null}
                    </TableCell>
                    <TableCell className="space-y-2">
                      <Input
                        type="number"
                        min="0"
                        step="0.01"
                        value={line.unitPrice}
                        onChange={(event) => updateLine(index, { unitPrice: event.target.value })}
                        disabled={disabled || !branchId}
                      />
                      {invalidUnitPrice ? (
                        <p className="text-xs text-red-600">Unit price must be 0 or more.</p>
                      ) : null}
                    </TableCell>
                    <TableCell className="text-sm font-medium">
                      {formatLineTotal(line.quantity, line.unitPrice)}
                    </TableCell>
                    <TableCell>
                      <Button
                        type="button"
                        variant="destructive"
                        onClick={() => removeLine(index)}
                        disabled={disabled}
                      >
                        Remove
                      </Button>
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </div>

      {!branchId ? (
        <p className="text-sm text-muted-foreground">Select a branch before adding sale lines.</p>
      ) : null}
      {itemsQuery.isError ? (
        <p className="text-sm text-red-600">Could not load branch-enabled items for this sale.</p>
      ) : null}

      <Button type="button" variant="outline" onClick={addLine} disabled={disabled || !branchId}>
        Add line
      </Button>
    </div>
  )
}
