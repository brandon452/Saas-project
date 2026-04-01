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
  useBTItemSearch,
} from "@/lib/hooks/branch-transfers/useBTItemSearch"

export interface TransferLineDraft {
  item: string
  item_name: string
  item_sku: string
  quantity_sent: number
}

interface TransferLineAddFormProps {
  orgId: string
  lines: TransferLineDraft[]
  onChange: (lines: TransferLineDraft[]) => void
  disabled?: boolean
}

export function TransferLineAddForm({
  orgId,
  lines,
  onChange,
  disabled,
}: TransferLineAddFormProps) {
  const [query, setQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [query])

  const itemSearchQuery = useBTItemSearch(orgId, debouncedQuery)

  const results = useMemo(() => {
    const existingItemIds = new Set(lines.map((line) => line.item))
    return (itemSearchQuery.data?.results ?? []).filter(
      (item) => !existingItemIds.has(item.id),
    )
  }, [lines, itemSearchQuery.data?.results])

  function addLine(item: { id: string; name: string; sku: string }) {
    onChange([
      ...lines,
      {
        item: item.id,
        item_name: item.name,
        item_sku: item.sku,
        quantity_sent: 1,
      },
    ])
    setQuery("")
    setDebouncedQuery("")
  }

  function updateLine(index: number, quantitySent: number) {
    onChange(
      lines.map((line, currentIndex) =>
        currentIndex === index ? { ...line, quantity_sent: quantitySent } : line,
      ),
    )
  }

  function removeLine(index: number) {
    onChange(lines.filter((_, currentIndex) => currentIndex !== index))
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
              <TableHead>Qty Sent</TableHead>
              <TableHead className="w-24">Remove</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {lines.length === 0 ? (
              <TableRow>
                <TableCell colSpan={3} className="text-center text-sm text-muted-foreground">
                  No lines added yet.
                </TableCell>
              </TableRow>
            ) : (
              lines.map((line, index) => (
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
                      value={String(line.quantity_sent)}
                      onChange={(event) =>
                        updateLine(index, Number.parseInt(event.target.value, 10) || 0)
                      }
                      disabled={disabled}
                    />
                    {line.quantity_sent <= 0 ? (
                      <p className="text-xs text-red-600">Quantity must be greater than 0.</p>
                    ) : null}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="destructive"
                      onClick={() => removeLine(index)}
                      disabled={disabled}
                    >
                      Remove
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="space-y-2">
        <Input
          placeholder="Search items by name or SKU"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          disabled={disabled}
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
                disabled={disabled}
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
