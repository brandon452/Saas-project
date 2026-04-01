"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { useState } from "react"

import { QuickSaleStatusBadge } from "@/components/quick-sales/QuickSaleStatusBadge"
import { ConfirmDialog } from "@/components/shared/ConfirmDialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useQuickSale } from "@/lib/hooks/quick-sales/useQuickSale"
import { useVoidQuickSale } from "@/lib/hooks/quick-sales/useQuickSaleMutations"
import { useOrg } from "@/lib/hooks/useOrg"

function formatCurrency(value: string | null) {
  if (!value) return "—"
  return Number.parseFloat(value).toFixed(2)
}

export default function QuickSaleDetailPage() {
  const params = useParams<{ orgId: string; id: string }>()
  const { orgId, canAccess, isParentUser } = useOrg()
  const saleId = params?.id ?? ""
  const quickSaleQuery = useQuickSale({ orgId, saleId })
  const voidQuickSale = useVoidQuickSale(orgId, saleId)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [actionError, setActionError] = useState("")

  const errorMessage = quickSaleQuery.error instanceof Error ? quickSaleQuery.error.message : ""

  async function handleVoid() {
    try {
      setActionError("")
      await voidQuickSale.mutateAsync()
      setConfirmOpen(false)
      await quickSaleQuery.refetch()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to void the quick sale.")
    }
  }

  if (quickSaleQuery.isLoading) {
    return <DetailSkeleton />
  }

  if (errorMessage.includes("404")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Quick sale not found</CardTitle>
        </CardHeader>
        <CardContent>
          <Link href={`/orgs/${orgId}/quick-sales`} className="text-sm text-primary">
            Back to quick sales
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (errorMessage.includes("403")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Access denied</CardTitle>
        </CardHeader>
        <CardContent>
          <Link href={`/orgs/${orgId}/quick-sales`} className="text-sm text-primary">
            Back to quick sales
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (!quickSaleQuery.data || quickSaleQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load quick sale</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">Try loading the page again.</p>
          <Button onClick={() => void quickSaleQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const sale = quickSaleQuery.data
  const canVoid = !isParentUser && canAccess(["OWNER", "ADMIN"]) && sale.status === "CONFIRMED"

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="space-y-2">
          <div className="text-sm text-muted-foreground">
            <Link href={`/orgs/${orgId}/quick-sales`} className="hover:text-foreground">
              Quick Sales
            </Link>{" "}
            / {new Date(sale.occurred_at).toLocaleString()}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">
              Sale - {new Date(sale.occurred_at).toLocaleString()}
            </h1>
            <QuickSaleStatusBadge status={sale.status} />
          </div>
        </div>
        <Link
          href={`/orgs/${orgId}/quick-sales`}
          className="inline-flex h-10 items-center justify-center rounded-md px-4 text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          Back
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Sale details</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm text-muted-foreground md:grid-cols-2">
          <p>Branch: {sale.branch.name}</p>
          <p>Customer: {sale.customer_name.trim() || "Walk-in"}</p>
          <p>Sold by: {sale.sold_by?.username ?? "—"}</p>
          <p>Date/time: {new Date(sale.occurred_at).toLocaleString()}</p>
          <p className="md:col-span-2">Notes: {sale.notes.trim() || "—"}</p>
          {sale.status === "VOIDED" ? (
            <>
              <p>Voided by: {sale.voided_by?.username ?? "—"}</p>
              <p>Voided at: {sale.voided_at ? new Date(sale.voided_at).toLocaleString() : "—"}</p>
            </>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Lines</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Item</TableHead>
                <TableHead>SKU</TableHead>
                <TableHead>Qty</TableHead>
                <TableHead>Unit Price</TableHead>
                <TableHead>Unit Cost</TableHead>
                <TableHead>Line Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sale.lines.map((line) => (
                <TableRow key={line.id}>
                  <TableCell>{line.item.name}</TableCell>
                  <TableCell className="font-mono text-sm">{line.item.sku}</TableCell>
                  <TableCell>{line.quantity}</TableCell>
                  <TableCell>{formatCurrency(line.unit_price)}</TableCell>
                  <TableCell>{formatCurrency(line.unit_cost)}</TableCell>
                  <TableCell>
                    {formatCurrency(
                      (
                        Number.parseFloat(line.quantity) * Number.parseFloat(line.unit_price)
                      ).toFixed(4),
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p className="text-sm font-medium">Total: {formatCurrency(sale.total_value)}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Actions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {canVoid ? (
            <Button disabled={voidQuickSale.isPending} onClick={() => setConfirmOpen(true)}>
              Void Sale
            </Button>
          ) : (
            <p className="text-sm text-muted-foreground">No actions available for this sale.</p>
          )}
          {actionError ? <p className="text-sm text-red-600">{actionError}</p> : null}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Void this sale?"
        description="Stock will be restored to the branch at the original cost."
        confirmLabel="Void sale"
        onConfirm={() => {
          void handleVoid()
        }}
        destructive
      />
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-52 w-full" />
      <Skeleton className="h-80 w-full" />
    </div>
  )
}
