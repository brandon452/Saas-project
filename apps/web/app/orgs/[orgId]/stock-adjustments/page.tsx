"use client"

import { useEffect, useMemo, useState } from "react"
import { Loader2, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { usePOBranches } from "@/lib/hooks/purchase-orders/usePOBranches"
import { useAdjustmentItemSearch } from "@/lib/hooks/stock-adjustments/useAdjustmentItemSearch"
import { useStockAdjustmentMutation } from "@/lib/hooks/stock-adjustments/useStockAdjustmentMutation"
import { useAuth } from "@/lib/hooks/useAuth"
import { useOrg } from "@/lib/hooks/useOrg"
import type { AdjustmentItemResult } from "@/lib/types/stock-adjustments"

function isNonZeroDecimalString(value: string): boolean {
  const trimmed = value.trim()
  if (!trimmed) return false
  if (!/^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(trimmed)) return false
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) && parsed !== 0
}

export default function StockAdjustmentsPage() {
  const { user, isLoading: authLoading } = useAuth()
  const { orgId, role } = useOrg()
  const branchesQuery = usePOBranches(orgId)

  const isStaff = role === "STAFF"
  const staffBranchId = useMemo(
    () => user?.memberships.find((membership) => membership.org_id === orgId)?.branch_id ?? "",
    [orgId, user?.memberships],
  )

  const [selectedBranchId, setSelectedBranchId] = useState("")
  const [itemInput, setItemInput] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [selectedItem, setSelectedItem] = useState<AdjustmentItemResult | null>(null)
  const [quantity, setQuantity] = useState("")
  const [reason, setReason] = useState("")
  const [submitError, setSubmitError] = useState("")
  const [successMessage, setSuccessMessage] = useState("")
  const [pendingIdempotencyKey, setPendingIdempotencyKey] = useState<string | null>(null)
  const [resultsOpen, setResultsOpen] = useState(false)

  const resolvedBranchId = isStaff ? staffBranchId : selectedBranchId
  const isBranchResolved = !!resolvedBranchId

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(itemInput.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [itemInput])

  useEffect(() => {
    if (!successMessage) return
    const timer = window.setTimeout(() => setSuccessMessage(""), 5000)
    return () => window.clearTimeout(timer)
  }, [successMessage])

  useEffect(() => {
    if (!isStaff) return
    setSelectedBranchId("")
  }, [isStaff])

  const itemSearchQuery = useAdjustmentItemSearch(orgId, resolvedBranchId, debouncedQuery)
  const searchResults = itemSearchQuery.data ?? []
  const adjustmentMutation = useStockAdjustmentMutation(orgId, resolvedBranchId)

  const quantityIsValid = isNonZeroDecimalString(quantity)
  const canSubmit = isBranchResolved && !!selectedItem && quantityIsValid && !adjustmentMutation.isPending

  function clearFeedback() {
    if (submitError) setSubmitError("")
    if (successMessage) setSuccessMessage("")
  }

  function resetForBranchChange(nextBranchId: string) {
    setSelectedBranchId(nextBranchId)
    setItemInput("")
    setDebouncedQuery("")
    setSelectedItem(null)
    setQuantity("")
    setReason("")
    setSubmitError("")
    setSuccessMessage("")
    setPendingIdempotencyKey(null)
    setResultsOpen(false)
  }

  function handleInteraction() {
    clearFeedback()
  }

  function handleSelectItem(item: AdjustmentItemResult) {
    clearFeedback()
    setSelectedItem(item)
    setItemInput("")
    setDebouncedQuery("")
    setResultsOpen(false)
  }

  function handleClearSelectedItem() {
    clearFeedback()
    setSelectedItem(null)
    setItemInput("")
    setDebouncedQuery("")
    setResultsOpen(false)
  }

  async function handleSubmit() {
    clearFeedback()

    if (!resolvedBranchId) {
      setSubmitError("Select a branch before posting an adjustment.")
      return
    }

    if (!selectedItem) {
      setSubmitError("Select an item before posting an adjustment.")
      return
    }

    if (!quantityIsValid) {
      setSubmitError("Enter a non-zero quantity.")
      return
    }

    const idempotencyKey = pendingIdempotencyKey ?? crypto.randomUUID()
    if (!pendingIdempotencyKey) {
      setPendingIdempotencyKey(idempotencyKey)
    }

    try {
      await adjustmentMutation.mutateAsync({
        item: selectedItem.id,
        quantity: quantity.trim(),
        movement_type: "ADJUSTMENT",
        reason: reason.trim() || undefined,
        idempotency_key: idempotencyKey,
      })
      setSuccessMessage("Adjustment posted successfully")
      setSelectedItem(null)
      setItemInput("")
      setDebouncedQuery("")
      setQuantity("")
      setReason("")
      setPendingIdempotencyKey(null)
      setResultsOpen(false)
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Failed to post adjustment.")
    }
  }

  if (authLoading || (!isStaff && branchesQuery.isLoading)) {
    return <StockAdjustmentsSkeleton />
  }

  const searchHelperText = !isBranchResolved
    ? "Select a branch first"
    : debouncedQuery.length < 2
      ? "Type at least 2 characters"
      : itemSearchQuery.isFetching
        ? "Loading"
        : itemSearchQuery.isError
          ? "Failed to load items"
          : searchResults.length === 0
            ? "No items found"
            : ""

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Stock Adjustments</h1>
        <p className="text-sm text-muted-foreground">
          Post manual inventory corrections for a branch and keep the movement ledger accurate.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>New adjustment</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {!isStaff ? (
            <div className="space-y-2">
              <Label htmlFor="adjustment-branch">Branch</Label>
              <select
                id="adjustment-branch"
                value={selectedBranchId}
                onChange={(event) => resetForBranchChange(event.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
                disabled={adjustmentMutation.isPending}
              >
                <option value="">Select a branch</option>
                {(branchesQuery.data ?? []).map((branch) => (
                  <option key={branch.id} value={branch.id}>
                    {branch.name}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div className="space-y-2">
              <Label>Branch</Label>
              <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-sm">
                {user?.memberships.find((membership) => membership.org_id === orgId)?.branch_name ?? "Assigned branch"}
              </div>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="adjustment-item-search">Item</Label>
            <div className="relative">
              <Input
                id="adjustment-item-search"
                value={itemInput}
                placeholder={isBranchResolved ? "Search items by name or SKU" : "Select a branch first"}
                onFocus={() => setResultsOpen(true)}
                onChange={(event) => {
                  handleInteraction()
                  setItemInput(event.target.value)
                  setResultsOpen(true)
                }}
                disabled={!isBranchResolved || adjustmentMutation.isPending}
              />

              {resultsOpen ? (
                <div className="absolute left-0 right-0 top-full z-20 mt-2 rounded-md border border-border bg-background shadow-lg">
                  {searchHelperText ? (
                    <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
                      {itemSearchQuery.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                      <span>{searchHelperText}</span>
                    </div>
                  ) : (
                    searchResults.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-accent"
                        onClick={() => handleSelectItem(item)}
                        disabled={adjustmentMutation.isPending}
                      >
                        <span className="font-medium">{item.name}</span>
                        <span className="text-muted-foreground">{item.sku}</span>
                      </button>
                    ))
                  )}
                </div>
              ) : null}
            </div>
          </div>

          {selectedItem ? (
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">
                {selectedItem.name} ({selectedItem.sku})
              </Badge>
              <Button
                type="button"
                variant="ghost"
                className="px-2"
                onClick={handleClearSelectedItem}
                disabled={adjustmentMutation.isPending}
              >
                <X className="h-4 w-4" />
                Clear
              </Button>
            </div>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="adjustment-quantity">Quantity</Label>
            <Input
              id="adjustment-quantity"
              inputMode="decimal"
              placeholder="e.g. 5 or -2.5"
              value={quantity}
              onChange={(event) => {
                handleInteraction()
                setQuantity(event.target.value)
              }}
              disabled={!selectedItem || adjustmentMutation.isPending}
            />
            <p className="text-sm text-muted-foreground">Positive to add stock, negative to remove</p>
            {quantity.trim() && !quantityIsValid ? (
              <p className="text-sm text-red-600">Quantity must be a non-zero decimal value.</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="adjustment-reason">Reason</Label>
            <Textarea
              id="adjustment-reason"
              placeholder="e.g. Damaged goods, count correction, found stock"
              value={reason}
              onChange={(event) => {
                handleInteraction()
                setReason(event.target.value)
              }}
              disabled={adjustmentMutation.isPending}
            />
          </div>

          {successMessage ? (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              {successMessage}
            </div>
          ) : null}

          {submitError ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {submitError}
            </div>
          ) : null}

          <div className="flex justify-end">
            <Button onClick={() => void handleSubmit()} disabled={!canSubmit}>
              {adjustmentMutation.isPending ? "Posting..." : "Post Adjustment"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function StockAdjustmentsSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-56" />
      <Skeleton className="h-[34rem] w-full" />
    </div>
  )
}
