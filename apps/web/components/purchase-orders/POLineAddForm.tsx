"use client"

import { useEffect, useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { usePOItemSearch } from "@/lib/hooks/purchase-orders/usePOItemSearch"
import type { Item } from "@/lib/types/purchase-orders"
import { formatPOValue } from "@/lib/utils/po"

interface AddLinePayload {
  itemId: number
  itemName: string
  itemSku: string
  ordered_quantity: number
  unit_price: string
}

interface POLineAddFormProps {
  orgId: string
  existingItemIds: number[]
  onAddLine: (payload: AddLinePayload) => void
  disabled?: boolean
  submitLabel?: string
}

export function POLineAddForm({
  orgId,
  existingItemIds,
  onAddLine,
  disabled,
  submitLabel = "Add Line",
}: POLineAddFormProps) {
  const [query, setQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [selectedItem, setSelectedItem] = useState<Item | null>(null)
  const [orderedQuantity, setOrderedQuantity] = useState("1")
  const [unitPrice, setUnitPrice] = useState("0.00")
  const [error, setError] = useState("")

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query), 300)
    return () => window.clearTimeout(timer)
  }, [query])

  const { data: items = [], isFetching } = usePOItemSearch(orgId, debouncedQuery)

  const helperText = useMemo(() => {
    if (debouncedQuery.length < 2) return "Type to search items..."
    if (isFetching) return "Loading items..."
    if (items.length === 0) return "No items found"
    return ""
  }, [debouncedQuery, isFetching, items.length])

  function resetForm() {
    setQuery("")
    setDebouncedQuery("")
    setSelectedItem(null)
    setOrderedQuantity("1")
    setUnitPrice("0.00")
    setError("")
  }

  function handleAdd() {
    const quantity = Number.parseInt(orderedQuantity, 10)
    const price = Number.parseFloat(unitPrice)

    if (!selectedItem) {
      setError("Select an item before adding a line.")
      return
    }

    if (existingItemIds.includes(selectedItem.id)) {
      setError("This item is already on the purchase order.")
      return
    }

    if (!Number.isInteger(quantity) || quantity <= 0) {
      setError("Ordered quantity must be greater than zero.")
      return
    }

    if (!Number.isFinite(price) || price <= 0) {
      setError("Unit price must be greater than zero.")
      return
    }

    onAddLine({
      itemId: selectedItem.id,
      itemName: selectedItem.name,
      itemSku: selectedItem.sku,
      ordered_quantity: quantity,
      unit_price: price.toFixed(2),
    })
    resetForm()
  }

  return (
    <div className="space-y-4 rounded-xl border border-border bg-card p-4">
      <div className="grid gap-4 md:grid-cols-[2fr_1fr_1fr_auto] md:items-end">
        <div className="space-y-2">
          <Label htmlFor="item-search">Item</Label>
          <Input
            id="item-search"
            placeholder="Search by item name or SKU"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value)
              setError("")
            }}
            disabled={disabled}
          />
          {selectedItem ? (
            <div className="rounded-md border border-border bg-muted px-3 py-2 text-sm">
              {selectedItem.name} ({selectedItem.sku})
            </div>
          ) : null}
          <div className="rounded-md border border-border bg-background">
            {helperText ? (
              <p className="px-3 py-2 text-sm text-muted-foreground">{helperText}</p>
            ) : (
              items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-accent"
                  onClick={() => {
                    setSelectedItem(item)
                    setQuery(item.name)
                    setError("")
                  }}
                  disabled={disabled}
                >
                  <span>{item.name}</span>
                  <span className="text-muted-foreground">{item.sku}</span>
                </button>
              ))
            )}
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="ordered-quantity">Ordered quantity</Label>
          <Input
            id="ordered-quantity"
            type="number"
            min="1"
            step="1"
            value={orderedQuantity}
            onChange={(event) => setOrderedQuantity(event.target.value)}
            disabled={disabled}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="unit-price">Unit price</Label>
          <Input
            id="unit-price"
            type="number"
            min="0.01"
            step="0.01"
            value={unitPrice}
            onChange={(event) => setUnitPrice(event.target.value)}
            disabled={disabled}
          />
        </div>

        <Button className="w-full md:w-auto" onClick={handleAdd} disabled={disabled}>
          {submitLabel}
        </Button>
      </div>

      {selectedItem && !error ? (
        <p className="text-sm text-muted-foreground">
          Line total preview:{" "}
          {formatPOValue(
            (Number.parseInt(orderedQuantity || "0", 10) || 0) *
              (Number.parseFloat(unitPrice || "0") || 0),
          )}
        </p>
      ) : null}

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
    </div>
  )
}
