"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"

import { DirectReceiptLineTable, type DirectReceiptLine } from "@/components/goods-receipts/DirectReceiptLineTable"
import { POReceiptLineTable, type POReceiptLineRow } from "@/components/goods-receipts/POReceiptLineTable"
import { POStatusBadge } from "@/components/purchase-orders/POStatusBadge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { useGRBranches } from "@/lib/hooks/goods-receipts/useGRBranches"
import { useCreateGoodsReceipt } from "@/lib/hooks/goods-receipts/useGoodsReceiptMutations"
import { useGRPOSearch, type GRPOSearchResult } from "@/lib/hooks/goods-receipts/useGRPOSearch"
import { useGRSuppliers } from "@/lib/hooks/goods-receipts/useGRSuppliers"
import { useAuth } from "@/lib/hooks/useAuth"
import { useOrg } from "@/lib/hooks/useOrg"
import type { ReceiptType } from "@/lib/types/goods-receipts"

export default function NewGoodsReceiptPage() {
  const router = useRouter()
  const { user } = useAuth()
  const { orgId, canAccess } = useOrg()
  const branchesQuery = useGRBranches(orgId)
  const suppliersQuery = useGRSuppliers(orgId)
  const createReceipt = useCreateGoodsReceipt(orgId)

  const [receiptType, setReceiptType] = useState<ReceiptType>("PO_RECEIPT")
  const [notes, setNotes] = useState("")

  const [poQuery, setPOQuery] = useState("")
  const [debouncedPOQuery, setDebouncedPOQuery] = useState("")
  const [selectedPO, setSelectedPO] = useState<GRPOSearchResult | null>(null)
  const [poLines, setPOLines] = useState<POReceiptLineRow[]>([])

  const [directBranch, setDirectBranch] = useState("")
  const [directSupplier, setDirectSupplier] = useState("")
  const [sourceReference, setSourceReference] = useState("")
  const [directLines, setDirectLines] = useState<DirectReceiptLine[]>([])

  const [submitError, setSubmitError] = useState("")

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedPOQuery(poQuery.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [poQuery])

  useEffect(() => {
    if (!orgId) return
    if (user?.parent_role === "PARENT_ADMIN" || user?.parent_role === "PARENT_VIEWER") {
      router.replace(`/orgs/${orgId}/goods-receipts/`)
      return
    }
    if (!canAccess(["OWNER", "ADMIN", "STAFF"])) {
      router.replace(`/orgs/${orgId}/goods-receipts/`)
    }
  }, [canAccess, orgId, router, user?.parent_role])

  const poSearchQuery = useGRPOSearch(orgId, debouncedPOQuery)
  const branchMap = new Map((branchesQuery.data ?? []).map((item) => [item.id, item.name]))
  const supplierMap = new Map((suppliersQuery.data ?? []).map((item) => [item.id, item.name]))

  const poSearchResults = useMemo(
    () => poSearchQuery.data?.results ?? [],
    [poSearchQuery.data?.results],
  )

  const allPOLinesReceived = selectedPO !== null && poLines.length === 0
  const hasInvalidPOLines = poLines.some(
    (line) => line.quantity_received <= 0 || line.quantity_received > line.remaining_quantity,
  )
  const hasInvalidDirectLines = directLines.some((line) => {
    const unitCost = Number.parseFloat(line.unit_cost)
    return line.quantity_received <= 0 || !line.unit_cost.trim() || !Number.isFinite(unitCost) || unitCost <= 0
  })
  const isPending = createReceipt.isPending

  function resetPOFields() {
    setPOQuery("")
    setDebouncedPOQuery("")
    setSelectedPO(null)
    setPOLines([])
  }

  function resetDirectFields() {
    setDirectBranch("")
    setDirectSupplier("")
    setSourceReference("")
    setDirectLines([])
  }

  function handleTypeChange(nextType: ReceiptType) {
    if (isPending || nextType === receiptType) return
    setSubmitError("")
    setReceiptType(nextType)
    if (nextType === "PO_RECEIPT") {
      resetDirectFields()
    } else {
      resetPOFields()
    }
  }

  function handleSelectPO(po: GRPOSearchResult) {
    const remainingLines = po.lines
      .map((line) => {
        const remainingQuantity = line.ordered_quantity - line.received_quantity
        return {
          po_line: line.id,
          item: line.item,
          ordered_quantity: line.ordered_quantity,
          remaining_quantity: remainingQuantity,
          quantity_received: remainingQuantity,
          unit_cost: line.unit_price,
        }
      })
      .filter((line) => line.remaining_quantity > 0)

    setSelectedPO(po)
    setPOQuery(po.po_number)
    setDebouncedPOQuery(po.po_number)
    setPOLines(remainingLines)
  }

  async function handleSubmit() {
    setSubmitError("")

    try {
      if (receiptType === "PO_RECEIPT") {
        if (!selectedPO) {
          setSubmitError("Select a purchase order before submitting.")
          return
        }
        if (allPOLinesReceived) {
          setSubmitError("All lines on this PO have been fully received.")
          return
        }
        if (hasInvalidPOLines) {
          setSubmitError("Fix the PO line quantities before submitting.")
          return
        }

        await createReceipt.mutateAsync({
          receipt_type: "PO_RECEIPT",
          purchase_order: selectedPO.id,
          notes,
          lines: poLines.map((line) => ({
            po_line: line.po_line,
            quantity_received: line.quantity_received,
            unit_cost: line.unit_cost.trim() ? line.unit_cost : null,
          })),
        })
        return
      }

      if (!directBranch) {
        setSubmitError("Branch is required for a direct receipt.")
        return
      }
      if (directLines.length === 0) {
        setSubmitError("Add at least one line before submitting.")
        return
      }
      if (hasInvalidDirectLines) {
        setSubmitError("Fix the direct receipt line values before submitting.")
        return
      }

      await createReceipt.mutateAsync({
        receipt_type: "DIRECT_RECEIPT",
        branch: directBranch,
        supplier: directSupplier || null,
        source_reference: sourceReference,
        notes,
        lines: directLines.map((line) => ({
          item: line.item,
          quantity_received: line.quantity_received,
          unit_cost: line.unit_cost,
        })),
      })
    } catch {
      setSubmitError("Failed to create the goods receipt.")
    }
  }

  if (user?.parent_role === "PARENT_ADMIN" || user?.parent_role === "PARENT_VIEWER") {
    return null
  }

  if (!canAccess(["OWNER", "ADMIN", "STAFF"])) {
    return null
  }

  if (branchesQuery.isLoading || suppliersQuery.isLoading) {
    return <CreateSkeleton />
  }

  const poSubmitDisabled =
    isPending || !selectedPO || allPOLinesReceived || poLines.length === 0 || hasInvalidPOLines
  const directSubmitDisabled =
    isPending || !directBranch || directLines.length === 0 || hasInvalidDirectLines

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="text-sm text-muted-foreground">
          <Link href={`/orgs/${orgId}/goods-receipts`} className="hover:text-foreground">
            Goods Receipts
          </Link>{" "}
          / New Goods Receipt
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">New Goods Receipt</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Receipt type</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <Button
              onClick={() => handleTypeChange("PO_RECEIPT")}
              disabled={isPending}
              className={receiptType === "PO_RECEIPT" ? "" : "bg-muted text-foreground hover:bg-muted/80"}
            >
              PO Receipt
            </Button>
            <Button
              onClick={() => handleTypeChange("DIRECT_RECEIPT")}
              disabled={isPending}
              className={receiptType === "DIRECT_RECEIPT" ? "" : "bg-muted text-foreground hover:bg-muted/80"}
            >
              Direct Receipt
            </Button>
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" value={notes} onChange={(event) => setNotes(event.target.value)} />
          </div>
        </CardContent>
      </Card>

      {receiptType === "PO_RECEIPT" ? (
        <Card>
          <CardHeader>
            <CardTitle>Purchase order receipt</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="po-search">Purchase order</Label>
              <Input
                id="po-search"
                placeholder="Search purchase orders"
                value={poQuery}
                onChange={(event) => {
                  setPOQuery(event.target.value)
                  setSubmitError("")
                }}
                disabled={isPending}
              />
              <div className="rounded-md border border-border bg-background">
                {debouncedPOQuery.length < 2 ? (
                  <p className="px-3 py-2 text-sm text-muted-foreground">Type at least 2 characters</p>
                ) : poSearchQuery.isFetching ? (
                  <p className="px-3 py-2 text-sm text-muted-foreground">Loading...</p>
                ) : poSearchResults.length === 0 ? (
                  <p className="px-3 py-2 text-sm text-muted-foreground">No results found</p>
                ) : (
                  poSearchResults.map((po) => (
                    <button
                      key={po.id}
                      type="button"
                      className="flex w-full flex-col gap-1 border-b border-border px-3 py-3 text-left last:border-b-0 hover:bg-accent"
                      onClick={() => handleSelectPO(po)}
                      disabled={isPending}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium">{po.po_number}</span>
                        <POStatusBadge status={po.status as never} />
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Supplier: {supplierMap.get(po.supplier) ?? "—"} | Branch: {branchMap.get(po.branch) ?? "—"}
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>

            {selectedPO ? (
              <div className="rounded-lg border border-border p-4">
                <div className="text-sm text-muted-foreground">
                  Selected PO: <span className="font-medium text-foreground">{selectedPO.po_number}</span>
                </div>
              </div>
            ) : null}

            <POReceiptLineTable lines={poLines} onChange={setPOLines} />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Direct receipt</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="branch">Branch</Label>
                <select
                  id="branch"
                  value={directBranch}
                  onChange={(event) => setDirectBranch(event.target.value)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
                  disabled={isPending}
                >
                  <option value="">Select branch</option>
                  {(branchesQuery.data ?? []).map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="supplier">Supplier</Label>
                <select
                  id="supplier"
                  value={directSupplier}
                  onChange={(event) => setDirectSupplier(event.target.value)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
                  disabled={isPending}
                >
                  <option value="">None</option>
                  {(suppliersQuery.data ?? []).map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="source_reference">Source reference</Label>
              <Input
                id="source_reference"
                placeholder="e.g. Shopee #123456, Pasar Borong KL"
                value={sourceReference}
                onChange={(event) => setSourceReference(event.target.value)}
                disabled={isPending}
              />
            </div>

            <DirectReceiptLineTable orgId={orgId} lines={directLines} onChange={setDirectLines} />
          </CardContent>
        </Card>
      )}

      {submitError ? <p className="text-sm text-red-600">{submitError}</p> : null}

      <div className="flex items-center justify-end gap-3">
        <Link
          href={`/orgs/${orgId}/goods-receipts`}
          className="inline-flex h-10 items-center justify-center rounded-md px-4 text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          Cancel
        </Link>
        <Button
          onClick={() => void handleSubmit()}
          disabled={receiptType === "PO_RECEIPT" ? poSubmitDisabled : directSubmitDisabled}
        >
          {isPending ? "Saving..." : "Create Goods Receipt"}
        </Button>
      </div>
    </div>
  )
}

function CreateSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-52 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
