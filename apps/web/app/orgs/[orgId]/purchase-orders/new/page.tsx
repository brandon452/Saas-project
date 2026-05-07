"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"

import { POLineAddForm } from "@/components/purchase-orders/POLineAddForm"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { usePOBranches } from "@/lib/hooks/purchase-orders/usePOBranches"
import { usePOMutations } from "@/lib/hooks/purchase-orders/usePOMutations"
import { usePOSuppliers } from "@/lib/hooks/purchase-orders/usePOSuppliers"
import { useOrg } from "@/lib/hooks/useOrg"
import { formatPOValue } from "@/lib/utils/po"

interface PendingLine {
  localId: string
  itemId: string
  itemName: string
  itemSku: string
  ordered_quantity: number
  unit_price: string
  persisted: boolean
}

export default function NewPurchaseOrderPage() {
  const router = useRouter()
  const { orgId, canAccess } = useOrg()
  const suppliersQuery = usePOSuppliers(orgId)
  const branchesQuery = usePOBranches(orgId)
  const { createPO, addLine } = usePOMutations(orgId)

  const [supplier, setSupplier] = useState("")
  const [branch, setBranch] = useState("")
  const [notes, setNotes] = useState("")
  const [pendingLines, setPendingLines] = useState<PendingLine[]>([])
  const [submitError, setSubmitError] = useState("")
  const [createdPOId, setCreatedPOId] = useState<string | null>(null)

  const isSubmitting = createPO.isPending || addLine.isPending
  const isLocked = createdPOId !== null || createPO.isPending

  useEffect(() => {
    if (!canAccess(["OWNER", "ADMIN"])) {
      router.replace(`/orgs/${orgId}/purchase-orders`)
    }
  }, [canAccess, orgId, router])

  function addPendingLine(line: Omit<PendingLine, "localId" | "persisted">) {
    setPendingLines((current) => [
      ...current,
      {
        ...line,
        localId: crypto.randomUUID(),
        persisted: false,
      },
    ])
  }

  function removePendingLine(localId: string) {
    if (isLocked) return
    setPendingLines((current) => current.filter((line) => line.localId !== localId))
  }

  async function handleSubmit() {
    setSubmitError("")

    if (!supplier || !branch) {
      setSubmitError("Supplier and branch are required.")
      return
    }

    if (pendingLines.length === 0) {
      setSubmitError("Add at least one line before creating the purchase order.")
      return
    }

    try {
      let poId = createdPOId

      if (!poId) {
        const po = await createPO.mutateAsync({
          supplier,
          branch,
          notes: notes || undefined,
        })
        poId = po.id
        setCreatedPOId(po.id)
      }

      for (const line of pendingLines) {
        if (line.persisted) continue

        await addLine.mutateAsync({
          poId,
          data: {
            item: line.itemId,
            ordered_quantity: line.ordered_quantity,
            unit_price: line.unit_price,
          },
        })

        setPendingLines((current) =>
          current.map((entry) =>
            entry.localId === line.localId ? { ...entry, persisted: true } : entry,
          ),
        )
      }

      router.push(`/orgs/${orgId}/purchase-orders/${poId}`)
    } catch {
      const failedLine = pendingLines.find((line) => !line.persisted)
      setSubmitError(
        failedLine
          ? `Failed while saving line for ${failedLine.itemName}. Fix the issue and retry.`
          : "Failed to create the purchase order.",
      )
    }
  }

  const total = useMemo(
    () =>
      pendingLines.reduce(
        (sum, line) => sum + line.ordered_quantity * Number.parseFloat(line.unit_price),
        0,
      ),
    [pendingLines],
  )

  if (!canAccess(["OWNER", "ADMIN"])) {
    return null
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="text-sm text-muted-foreground">
          <Link href={`/orgs/${orgId}/purchase-orders`} className="hover:text-foreground">
            Purchase Orders
          </Link>{" "}
          / New Purchase Order
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">New Purchase Order</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Purchase order header</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="supplier">Supplier</Label>
            <select
              id="supplier"
              value={supplier}
              onChange={(event) => setSupplier(event.target.value)}
              disabled={isLocked}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
            >
              <option value="">Select supplier</option>
              {(suppliersQuery.data ?? []).filter((s) => s.is_active).map((option) => (
                <option key={option.id} value={String(option.id)}>
                  {option.display_name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="branch">Branch</Label>
            <select
              id="branch"
              value={branch}
              onChange={(event) => setBranch(event.target.value)}
              disabled={isLocked}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
            >
              <option value="">Select branch</option>
              {(branchesQuery.data ?? []).map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2 md:col-span-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea
              id="notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              disabled={isLocked}
            />
          </div>
        </CardContent>
      </Card>

      <POLineAddForm
        orgId={orgId}
        supplierId={supplier}
        existingItemIds={pendingLines.map((line) => line.itemId)}
        onAddLine={addPendingLine}
        disabled={isLocked}
      />

      <Card>
        <CardHeader>
          <CardTitle>Pending lines</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {pendingLines.length === 0 ? (
            <p className="text-sm text-muted-foreground">No lines added yet.</p>
          ) : (
            pendingLines.map((line) => (
              <div
                key={line.localId}
                className="flex flex-col gap-3 rounded-lg border border-border p-4 md:flex-row md:items-center md:justify-between"
              >
                <div>
                  <p className="font-medium">{line.itemName}</p>
                  <p className="text-sm text-muted-foreground">{line.itemSku}</p>
                </div>
                <div className="text-sm text-muted-foreground">
                  Qty {line.ordered_quantity} x {formatPOValue(parseFloat(line.unit_price))} ={" "}
                  {formatPOValue(line.ordered_quantity * parseFloat(line.unit_price))}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    {line.persisted ? "Saved" : "Pending"}
                  </span>
                  <Button
                    variant="destructive"
                    onClick={() => removePendingLine(line.localId)}
                    disabled={isLocked}
                  >
                    Remove
                  </Button>
                </div>
              </div>
            ))
          )}

          <div className="flex flex-col gap-4 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              Running total: <span className="font-medium text-foreground">{formatPOValue(total)}</span>
            </p>
            <div className="flex items-center gap-3">
              <Link
                href={`/orgs/${orgId}/purchase-orders`}
                className="inline-flex h-10 items-center justify-center rounded-md px-4 text-sm font-medium text-muted-foreground hover:text-foreground"
              >
                Cancel
              </Link>
              <Button onClick={handleSubmit} disabled={isSubmitting}>
                {isSubmitting ? "Saving..." : "Create Purchase Order"}
              </Button>
            </div>
          </div>

          {submitError ? <p className="text-sm text-red-600">{submitError}</p> : null}
        </CardContent>
      </Card>
    </div>
  )
}
