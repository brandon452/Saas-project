"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { ScanLine } from "lucide-react"

import { PickScanMode } from "@/components/scan-modes/PickScanMode"
import { SaleLineEditor, type SaleLineDraft } from "@/components/quick-sales/SaleLineEditor"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { useBranches } from "@/lib/hooks/branches/useBranches"
import { useCreateQuickSale } from "@/lib/hooks/quick-sales/useQuickSaleMutations"
import { useAuth } from "@/lib/hooks/useAuth"
import { useOrg } from "@/lib/hooks/useOrg"
import type { CreateQuickSalePayload } from "@/lib/types/quick-sales"

function toDateInputString(date: Date) {
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return localDate.toISOString().slice(0, 10)
}

function toOccurredAtIsoFromDate(dateValue: string) {
  const [year, month, day] = dateValue.split("-").map(Number)
  return new Date(year, month - 1, day, 12, 0, 0, 0).toISOString()
}

export default function NewQuickSalePage() {
  const router = useRouter()
  const { user } = useAuth()
  const { orgId, isParentUser } = useOrg()
  const branchesQuery = useBranches(orgId)
  const createQuickSale = useCreateQuickSale(orgId)

  const [branchId, setBranchId] = useState("")
  const [customerName, setCustomerName] = useState("")
  const [notes, setNotes] = useState("")
  const [useCustomOccurredAt, setUseCustomOccurredAt] = useState(false)
  const [occurredAt, setOccurredAt] = useState(toDateInputString(new Date()))
  const [lines, setLines] = useState<SaleLineDraft[]>([{ itemId: "", quantity: "", unitPrice: "" }])
  const [submitError, setSubmitError] = useState("")
  const [scanModeOpen, setScanModeOpen] = useState(false)

  useEffect(() => {
    if (!orgId) return
    if (isParentUser || user?.parent_role) {
      router.replace(`/orgs/${orgId}/quick-sales`)
    }
  }, [isParentUser, orgId, router, user?.parent_role])

  const runningTotal = useMemo(() => {
    return lines.reduce((sum, line) => {
      const quantity = Number.parseFloat(line.quantity)
      const unitPrice = Number.parseFloat(line.unitPrice)
      if (!Number.isFinite(quantity) || !Number.isFinite(unitPrice)) return sum
      return sum + quantity * unitPrice
    }, 0)
  }, [lines])

  async function handleSubmit() {
    setSubmitError("")

    if (!branchId) {
      setSubmitError("Branch is required.")
      return
    }

    if (useCustomOccurredAt && occurredAt) {
      const selectedDate = new Date(`${occurredAt}T12:00:00`)
      const today = new Date()
      today.setHours(23, 59, 59, 999)
      if (selectedDate.getTime() > today.getTime()) {
        setSubmitError("Sale date cannot be in the future.")
        return
      }
    }

    if (lines.length === 0) {
      setSubmitError("Add at least one line before confirming the sale.")
      return
    }

    for (const line of lines) {
      const quantity = Number.parseFloat(line.quantity)
      const unitPrice = Number.parseFloat(line.unitPrice)
      if (!line.itemId || !Number.isFinite(quantity) || quantity <= 0) {
        setSubmitError("Each line must include an item and a quantity greater than 0.")
        return
      }
      if (!Number.isFinite(unitPrice) || unitPrice < 0) {
        setSubmitError("Each line must include a unit price of 0 or more.")
        return
      }
    }

    const payload: CreateQuickSalePayload = {
      branch: branchId,
      customer_name: customerName,
      notes,
      occurred_at:
        useCustomOccurredAt && occurredAt
          ? toOccurredAtIsoFromDate(occurredAt)
          : undefined,
      lines: lines.map((line) => ({
        item: line.itemId,
        quantity: line.quantity,
        unit_price: line.unitPrice,
      })),
    }

    try {
      const sale = await createQuickSale.mutateAsync(payload)
      router.push(`/orgs/${orgId}/quick-sales/${sale.id}`)
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Failed to create the quick sale.")
    }
  }

  if (isParentUser || user?.parent_role) {
    return null
  }

  if (branchesQuery.isLoading) {
    return <CreateSkeleton />
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="text-sm text-muted-foreground">
          <Link href={`/orgs/${orgId}/quick-sales`} className="hover:text-foreground">
            Quick Sales
          </Link>{" "}
          / New Sale
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">New Sale</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Sale details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="branch">Branch</Label>
              <select
                id="branch"
                value={branchId}
                onChange={(event) => setBranchId(event.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
                disabled={createQuickSale.isPending}
              >
                <option value="">Select branch</option>
                {(branchesQuery.data ?? []).map((branch) => (
                  <option key={branch.id} value={branch.id}>
                    {branch.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label>Sale time</Label>
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  checked={useCustomOccurredAt}
                  onChange={(event) => setUseCustomOccurredAt(event.target.checked)}
                  disabled={createQuickSale.isPending}
                />
                Set custom sale date
              </label>
              {useCustomOccurredAt ? (
                <Input
                  id="occurred_at"
                  type="date"
                  value={occurredAt}
                  onChange={(event) => setOccurredAt(event.target.value)}
                  max={toDateInputString(new Date())}
                  disabled={createQuickSale.isPending}
                />
              ) : (
                <p className="text-sm text-muted-foreground">
                  If left off, the sale will use the current time automatically.
                </p>
              )}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="customer_name">Customer name</Label>
              <Input
                id="customer_name"
                value={customerName}
                onChange={(event) => setCustomerName(event.target.value)}
                placeholder="Walk-in"
                disabled={createQuickSale.isPending}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                disabled={createQuickSale.isPending}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {branchId && (
        <div className="flex justify-end">
          <Button
            type="button"
            variant={scanModeOpen ? "ghost" : "outline"}
            size="sm"
            onClick={() => setScanModeOpen((v) => !v)}
            disabled={createQuickSale.isPending}
          >
            <ScanLine className="mr-2 h-4 w-4" />
            {scanModeOpen ? "Manual Mode" : "Scan Mode"}
          </Button>
        </div>
      )}

      {scanModeOpen && branchId && (
        <PickScanMode
          orgId={orgId}
          branchId={branchId}
          isPending={createQuickSale.isPending}
          onSubmit={async (payload) => {
            const sale = await createQuickSale.mutateAsync(payload)
            router.push(`/orgs/${orgId}/quick-sales/${sale.id}`)
          }}
        />
      )}

      {!scanModeOpen && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Sale lines</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <SaleLineEditor
                orgId={orgId}
                branchId={branchId}
                lines={lines}
                onChange={setLines}
                disabled={createQuickSale.isPending}
              />
              <p className="text-sm font-medium">Total: {runningTotal.toFixed(2)}</p>
            </CardContent>
          </Card>

          {submitError ? <p className="text-sm text-red-600">{submitError}</p> : null}

          <div className="flex items-center justify-end gap-3">
            <Link
              href={`/orgs/${orgId}/quick-sales`}
              className="inline-flex h-10 items-center justify-center rounded-md px-4 text-sm font-medium text-muted-foreground hover:text-foreground"
            >
              Cancel
            </Link>
            <Button onClick={() => void handleSubmit()} disabled={createQuickSale.isPending}>
              {createQuickSale.isPending ? "Saving..." : "Confirm Sale"}
            </Button>
          </div>
        </>
      )}
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
