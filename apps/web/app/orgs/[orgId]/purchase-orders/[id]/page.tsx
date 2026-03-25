"use client"

import Link from "next/link"
import { useState } from "react"
import { useParams, useRouter } from "next/navigation"

import { POLineAddForm } from "@/components/purchase-orders/POLineAddForm"
import { POLineTable } from "@/components/purchase-orders/POLineTable"
import { POStatusBadge } from "@/components/purchase-orders/POStatusBadge"
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
import { usePOBranches } from "@/lib/hooks/purchase-orders/usePOBranches"
import { usePOMutations } from "@/lib/hooks/purchase-orders/usePOMutations"
import { usePurchaseOrder } from "@/lib/hooks/purchase-orders/usePurchaseOrder"
import { usePOSuppliers } from "@/lib/hooks/purchase-orders/usePOSuppliers"
import { useOrg } from "@/lib/hooks/useOrg"
import { calculatePOTotal, formatPOValue } from "@/lib/utils/po"

export default function PurchaseOrderDetailPage() {
  const router = useRouter()
  const params = useParams<{ orgId: string; id: string }>()
  const { orgId } = useOrg()
  const poId = params?.id ?? ""

  const purchaseOrderQuery = usePurchaseOrder(orgId, poId)
  const suppliersQuery = usePOSuppliers(orgId)
  const branchesQuery = usePOBranches(orgId)
  const { submitPO, cancelPO, addLine, updateLine, removeLine } = usePOMutations(orgId)

  const [submitDialogOpen, setSubmitDialogOpen] = useState(false)
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
  const [lineActionError, setLineActionError] = useState("")

  const po = purchaseOrderQuery.data

  const supplierMap = new Map((suppliersQuery.data ?? []).map((item) => [item.id, item.name]))
  const branchMap = new Map((branchesQuery.data ?? []).map((item) => [item.id, item.name]))

  const errorMessage = purchaseOrderQuery.error instanceof Error ? purchaseOrderQuery.error.message : ""
  const isDraft = po?.status === "DRAFT"
  const isActionPending =
    submitPO.isPending ||
    cancelPO.isPending ||
    addLine.isPending ||
    updateLine.isPending ||
    removeLine.isPending

  async function handleUpdateLine(
    lineId: number,
    data: Partial<{ ordered_quantity: number; unit_price: string }>,
  ) {
    if (!po) return
    await updateLine.mutateAsync({
      poId: po.id,
      lineId,
      data,
    })
  }

  async function handleRemoveLine(lineId: number) {
    if (!po) return
    try {
      setLineActionError("")
      await removeLine.mutateAsync({ poId: po.id, lineId })
    } catch {
      setLineActionError("Failed to remove the line.")
    }
  }

  async function handleAddLine(payload: {
    itemId: string
    itemName: string
    itemSku: string
    ordered_quantity: number
    unit_price: string
  }) {
    if (!po) return
    try {
      setLineActionError("")
      await addLine.mutateAsync({
        poId: po.id,
        data: {
          item: payload.itemId,
          ordered_quantity: payload.ordered_quantity,
          unit_price: payload.unit_price,
        },
      })
    } catch {
      setLineActionError("Failed to add the new line.")
    }
  }

  if (purchaseOrderQuery.isLoading || suppliersQuery.isLoading || branchesQuery.isLoading) {
    return <DetailSkeleton />
  }

  if (errorMessage.includes("404")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Purchase order not found</CardTitle>
        </CardHeader>
        <CardContent>
          <Link href={`/orgs/${orgId}/purchase-orders`} className="text-sm text-primary">
            Back to purchase orders
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
          <Link href={`/orgs/${orgId}/purchase-orders`} className="text-sm text-primary">
            Back to purchase orders
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (!po || purchaseOrderQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load purchase order</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">Try loading the page again.</p>
          <Button onClick={() => void purchaseOrderQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="text-sm text-muted-foreground">
          <Link href={`/orgs/${orgId}/purchase-orders`} className="hover:text-foreground">
            Purchase Orders
          </Link>{" "}
          / {po.po_number}
        </div>
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="space-y-3">
            <CardTitle>{po.po_number}</CardTitle>
            <div className="grid gap-2 text-sm text-muted-foreground">
              <p>Supplier: {supplierMap.get(po.supplier) ?? "—"}</p>
              <p>Branch: {branchMap.get(po.branch) ?? "—"}</p>
              <p>Created by: {po.created_by ?? "—"}</p>
              <p>Created at: {new Date(po.created_at).toLocaleString()}</p>
            </div>
          </div>
          <div className="flex flex-col items-start gap-3 md:items-end">
            <POStatusBadge status={po.status} />
            <div className="text-right">
              <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Total value</p>
              <p className="text-2xl font-semibold">{formatPOValue(calculatePOTotal(po.lines))}</p>
            </div>
            <div className="flex gap-3">
              {po.status === "DRAFT" ? (
                <>
                  <Button disabled={isActionPending} onClick={() => setSubmitDialogOpen(true)}>
                    Submit
                  </Button>
                  <Button variant="ghost" disabled={isActionPending} onClick={() => setCancelDialogOpen(true)}>
                    Cancel
                  </Button>
                </>
              ) : null}
              {po.status === "SUBMITTED" ? (
                <Button variant="ghost" disabled={isActionPending} onClick={() => setCancelDialogOpen(true)}>
                  Cancel
                </Button>
              ) : null}
            </div>
          </div>
        </CardHeader>
      </Card>

      {po.notes ? (
        <Card>
          <CardHeader>
            <CardTitle>Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{po.notes}</p>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Lines</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <POLineTable
            lines={po.lines}
            editable={isDraft}
            busy={isActionPending}
            onUpdateLine={handleUpdateLine}
            onRemoveLine={handleRemoveLine}
          />
          {lineActionError ? <p className="text-sm text-red-600">{lineActionError}</p> : null}
        </CardContent>
      </Card>

      {po.receipts.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Receipts</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Received By</TableHead>
                  <TableHead>Lines</TableHead>
                  <TableHead>Total Qty</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {po.receipts.map((receipt) => (
                  <TableRow key={receipt.id}>
                    <TableCell>{new Date(receipt.received_at).toLocaleString()}</TableCell>
                    <TableCell>{receipt.received_by ?? "—"}</TableCell>
                    <TableCell>{receipt.line_count}</TableCell>
                    <TableCell>{receipt.total_quantity_received}</TableCell>
                    <TableCell>
                      <Link
                        href={`/orgs/${orgId}/goods-receipts/${receipt.id}`}
                        className="text-sm text-primary hover:underline"
                      >
                        View
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : null}

      {isDraft ? (
        <POLineAddForm
          orgId={orgId}
          existingItemIds={po.lines.map((line) => line.item.id)}
          onAddLine={(payload) => void handleAddLine(payload)}
          disabled={isActionPending}
        />
      ) : null}

      <ConfirmDialog
        open={submitDialogOpen}
        onOpenChange={setSubmitDialogOpen}
        title="Submit Purchase Order"
        description="Once submitted this order cannot be edited. Are you sure?"
        confirmLabel="Submit"
        onConfirm={() => {
          void submitPO.mutateAsync(po.id).then(() => router.refresh())
        }}
      />

      <ConfirmDialog
        open={cancelDialogOpen}
        onOpenChange={setCancelDialogOpen}
        title="Cancel Purchase Order"
        description="This will cancel the purchase order. This cannot be undone."
        confirmLabel="Cancel Order"
        onConfirm={() => {
          void cancelPO.mutateAsync(po.id).then(() => router.refresh())
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
