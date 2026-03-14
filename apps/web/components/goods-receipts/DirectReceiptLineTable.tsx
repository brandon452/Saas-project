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
import {
  useGRItemSearch,
  type GRItemSearchResult,
} from "@/lib/hooks/goods-receipts/useGRItemSearch"

export interface DirectReceiptLine {
  item: string
  item_name: string
  item_sku: string
  quantity_received: number
  unit_cost: string
}

interface DirectReceiptLineTableProps {
  orgId: string
  lines: DirectReceiptLine[]
  onChange: (lines: DirectReceiptLine[]) => void
}

export function DirectReceiptLineTable({ orgId, lines, onChange }: DirectReceiptLineTableProps) {
  const [query, setQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [query])

  const itemSearchQuery = useGRItemSearch(orgId, debouncedQuery)

  const results = useMemo(() => {
    const existingItemIds = new Set(lines.map((line) => line.item))
    return (itemSearchQuery.data?.results ?? []).filter((item) => !existingItemIds.has(item.id))
  }, [lines, itemSearchQuery.data?.results])

  function updateLine(index: number, patch: Partial<DirectReceiptLine>) {
    onChange(lines.map((line, currentIndex) => (currentIndex === index ? { ...line, ...patch } : line)))
  }

  function removeLine(index: number) {
    onChange(lines.filter((_, currentIndex) => currentIndex !== index))
  }

  function addLine(item: GRItemSearchResult) {
    onChange([
      ...lines,
      {
        item: item.id,
        item_name: item.name,
        item_sku: item.sku,
        quantity_received: 1,
        unit_cost: "",
      },
    ])
    setQuery("")
    setDebouncedQuery("")
  }

  const helperText =
    debouncedQuery.length < 2
      ? "Type at least 2 characters"
      : itemSearchQuery.isFetching
        ? "Loading..."
        : results.length === 0
          ? "No results found"
          : ""

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Item</TableHead>
              <TableHead>Qty</TableHead>
              <TableHead>Unit Cost</TableHead>
              <TableHead className="w-24">Remove</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {lines.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-sm text-muted-foreground">
                  No lines added yet.
                </TableCell>
              </TableRow>
            ) : (
              lines.map((line, index) => {
                const invalidQuantity = line.quantity_received <= 0
                const parsedUnitCost = Number.parseFloat(line.unit_cost)
                const invalidUnitCost =
                  !line.unit_cost.trim() || !Number.isFinite(parsedUnitCost) || parsedUnitCost <= 0

                return (
                  <TableRow key={line.item}>
                    <TableCell>
                      <div className="font-medium">{line.item_name}</div>
                      <div className="text-sm text-muted-foreground">{line.item_sku}</div>
                    </TableCell>
                    <TableCell className="space-y-2">
                      <Input
                        type="number"
                        min="1"
                        step="1"
                        value={String(line.quantity_received)}
                        onChange={(event) =>
                          updateLine(index, {
                            quantity_received: Number.parseInt(event.target.value, 10) || 0,
                          })
                        }
                      />
                      {invalidQuantity ? (
                        <p className="text-xs text-red-600">Quantity must be greater than 0.</p>
                      ) : null}
                    </TableCell>
                    <TableCell className="space-y-2">
                      <Input
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={line.unit_cost}
                        onChange={(event) => updateLine(index, { unit_cost: event.target.value })}
                      />
                      {invalidUnitCost ? (
                        <p className="text-xs text-red-600">Unit cost must be greater than 0.</p>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        className="text-red-600 hover:text-red-700"
                        onClick={() => removeLine(index)}
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

      <div className="space-y-2">
        <Input
          placeholder="Search items by name or SKU"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <div className="rounded-md border border-border bg-background">
          {helperText ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">{helperText}</p>
          ) : (
            results.map((item) => (
              <button
                key={item.id}
                type="button"
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-accent"
                onClick={() => addLine(item)}
              >
                <span>{item.name}</span>
                <span className="text-muted-foreground">{item.sku}</span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
