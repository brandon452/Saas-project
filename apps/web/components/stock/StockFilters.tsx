"use client"

import { useEffect, useMemo, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Loader2, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useStockItemSearch } from "@/lib/hooks/stock/useStockItemSearch"

interface StockFiltersProps {
  branches: { id: string; name: string }[]
  orgId: string
  selectedBranchId?: string
}

export function StockFilters({
  branches,
  orgId,
  selectedBranchId,
}: StockFiltersProps) {
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  const itemParam = searchParams.get("item") ?? ""
  const branchParam = searchParams.get("branch") ?? selectedBranchId ?? ""

  const [itemInput, setItemInput] = useState("")
  const [selectedItemLabel, setSelectedItemLabel] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [isResultsOpen, setIsResultsOpen] = useState(false)

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const nextQuery =
        selectedItemLabel && itemInput === selectedItemLabel ? "" : itemInput.trim()
      setDebouncedQuery(nextQuery)
    }, 300)

    return () => window.clearTimeout(timer)
  }, [itemInput, selectedItemLabel])

  useEffect(() => {
    if (!itemParam) {
      setSelectedItemLabel("")
    }
  }, [itemParam])

  const itemSearchQuery = useStockItemSearch(
    orgId,
    debouncedQuery,
    branchParam || undefined,
  )

  const searchResults = useMemo(
    () => itemSearchQuery.data?.results ?? [],
    [itemSearchQuery.data?.results],
  )

  useEffect(() => {
    if (!itemParam || selectedItemLabel) return

    const match = searchResults.find((result) => result.id === itemParam)
    if (!match) return

    const label = `${match.name} (${match.sku})`
    setSelectedItemLabel(label)
    setItemInput(label)
  }, [itemParam, searchResults, selectedItemLabel])

  const helperText = useMemo(() => {
    if (selectedItemLabel && itemInput === selectedItemLabel) return ""
    if (itemParam && !selectedItemLabel && itemInput.trim().length < 2) {
      return "Selected item"
    }
    if (itemInput.trim().length < 2) return "Type at least 2 characters"
    if (itemSearchQuery.isFetching) return "Loading"
    if (searchResults.length === 0) return "No items found"
    return ""
  }, [itemInput, itemParam, itemSearchQuery.isFetching, searchResults.length, selectedItemLabel])

  function replaceParams(next: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString())

    for (const [key, value] of Object.entries(next)) {
      if (!value) {
        params.delete(key)
      } else {
        params.set(key, value)
      }
    }

    const query = params.toString()
    router.replace(query ? `${pathname}?${query}` : pathname)
  }

  function handleBranchChange(nextBranchId: string) {
    setItemInput("")
    setSelectedItemLabel("")
    setDebouncedQuery("")
    setIsResultsOpen(false)
    replaceParams({
      branch: nextBranchId || null,
      item: null,
      page: "1",
    })
  }

  function handleItemInputChange(nextValue: string) {
    const wasSelected = !!itemParam && !!selectedItemLabel

    setItemInput(nextValue)
    setIsResultsOpen(true)

    if (!nextValue.trim()) {
      setSelectedItemLabel("")
      if (itemParam) {
        replaceParams({ item: null, page: "1" })
      }
      return
    }

    if (wasSelected && nextValue !== selectedItemLabel) {
      setSelectedItemLabel("")
      replaceParams({ item: null, page: "1" })
    }
  }

  function handleSelectItem(item: { id: string; name: string; sku: string }) {
    const label = `${item.name} (${item.sku})`
    setSelectedItemLabel(label)
    setItemInput(label)
    setDebouncedQuery("")
    setIsResultsOpen(false)
    replaceParams({ item: item.id, page: "1" })
  }

  function clearItemFilter() {
    setItemInput("")
    setSelectedItemLabel("")
    setDebouncedQuery("")
    setIsResultsOpen(false)
    replaceParams({ item: null, page: "1" })
  }

  function clearAllFilters() {
    setItemInput("")
    setSelectedItemLabel("")
    setDebouncedQuery("")
    setIsResultsOpen(false)
    replaceParams({
      branch: null,
      item: null,
      page: null,
    })
  }

  return (
    <div className="grid gap-4 rounded-xl border border-border bg-card p-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,14rem),1fr))]">
      <div className="space-y-2">
        <label htmlFor="stock-branch" className="text-sm font-medium">
          Branch
        </label>
        <select
          id="stock-branch"
          value={branchParam}
          onChange={(event) => handleBranchChange(event.target.value)}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
        >
          <option value="">All branches</option>
          {branches.map((branch) => (
            <option key={branch.id} value={branch.id}>
              {branch.name}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <label htmlFor="stock-item" className="text-sm font-medium">
          Item
        </label>
        <div className="relative">
          <div className="flex min-w-0 items-center gap-2">
            <Input
              id="stock-item"
              className="min-w-0"
              value={itemInput}
              placeholder={itemParam && !selectedItemLabel ? "Selected item" : "Search items by name or SKU"}
              onFocus={() => setIsResultsOpen(true)}
              onChange={(event) => handleItemInputChange(event.target.value)}
            />
            {itemParam ? (
              <Button
                type="button"
                variant="ghost"
                className="px-2 py-2"
                onClick={clearItemFilter}
                aria-label="Clear selected item"
              >
                <X className="h-4 w-4" />
              </Button>
            ) : null}
          </div>

          {isResultsOpen ? (
            <div className="absolute left-0 right-0 top-full z-20 mt-2 rounded-md border border-border bg-background shadow-lg">
              {helperText ? (
                <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
                  {itemSearchQuery.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  <span>{helperText}</span>
                </div>
              ) : (
                searchResults.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-accent"
                    onClick={() => handleSelectItem(item)}
                  >
                    <span>{item.name}</span>
                    <span className="text-muted-foreground">{item.sku}</span>
                  </button>
                ))
              )}
            </div>
          ) : null}
        </div>
      </div>

      <div className="flex items-end">
        <Button type="button" variant="ghost" className="w-full" onClick={clearAllFilters}>
          Clear all filters
        </Button>
      </div>
    </div>
  )
}
