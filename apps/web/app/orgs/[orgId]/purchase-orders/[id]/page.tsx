"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"

import { POLineAddForm } from "@/components/purchase-orders/POLineAddForm"
import { POLineTable } from "@/components/purchase-orders/POLineTable"
import { POStatusBadge } from "@/components/purchase-orders/POStatusBadge"
import { ConfirmDialog } from "@/components/shared/ConfirmDialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { usePOBranches } from "@/lib/hooks/purchase-orders/usePOBranches"
import { usePOMutations } from "@/lib/hooks/purchase-orders/usePOMutations"
import { usePurchaseOrder } from "@/lib/hooks/purchase-orders/usePurchaseOrder"
import { usePOSuppliers } from "@/lib/hooks/purchase-orders/usePOSuppliers"
import { useOrg } from "@/lib/hooks/useOrg"
import { calculatePOTotal, formatPOValue } from "@/lib/utils/po"
import { downloadPdf } from "@/lib/utils/download-pdf"

export default function PurchaseOrderDetailPage() {
  const router = useRouter()
  const params = useParams<{ orgId: string; id: string }>()
  const { orgId, canAccess } = useOrg()
  const poId = params?.id ?? ""

  const purchaseOrderQuery = usePurchaseOrder(orgId, poId)
  const suppliersQuery = usePOSuppliers(orgId)
  const branchesQuery = usePOBranches(orgId)
  const { updatePO, submitPO, cancelPO, addLine, updateLine, removeLine } = usePOMutations(orgId)

  const [pdfStatus, setPdfStatus] = useState<"idle" | "loading" | "success" | "error">("idle")
  const [pdfError, setPdfError] = useState<string | null>(null)
  const [submitDialogOpen, setSubmitDialogOpen] = useState(false)
  const [submitError, setSubmitError] = useState("")
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
  const [cancelError, setCancelError] = useState("")
  const [lineActionError, setLineActionError] = useState("")
  const [lineActionWarning, setLineActionWarning] = useState("")
  const [headerError, setHeaderError] = useState("")
  const [editSupplier, setEditSupplier] = useState("")
  const [editBranch, setEditBranch] = useState("")
  const [editNotes, setEditNotes] = useState("")

  const po = purchaseOrderQuery.data

  const supplierMap = new Map((suppliersQuery.data ?? []).map((item) => [String(item.id), item.display_name]))
  const branchMap = new Map((branchesQuery.data ?? []).map((item) => [item.id, item.name]))

  const errorMessage = purchaseOrderQuery.error instanceof Error ? purchaseOrderQuery.error.message : ""
  const isDraft = po?.status === "DRAFT"
  const isActionPending =
    updatePO.isPending ||
    submitPO.isPending ||
    cancelPO.isPending ||
    addLine.isPending ||
    updateLine.isPending ||
    removeLine.isPending

  useEffect(() => {
    if (po) {
      setEditSupplier(po.supplier)
      setEditBranch(po.branch)
      setEditNotes(po.notes)
    }
  }, [po])

  async function handleSaveHeader() {
    if (!po) return
    const data: { supplier?: string; branch?: string; notes?: string } = {}
    if (editSupplier !== po.supplier) data.supplier = editSupplier
    if (editBranch !== po.branch) data.branch = editBranch
    if (editNotes !== po.notes) data.notes = editNotes
    if (Object.keys(data).length === 0) return
    try {
      setHeaderError("")
      await updatePO.mutateAsync({ poId: po.id, data })
    } catch {
      setHeaderError("Failed to save header changes.")
    }
  }

  const headerChanged =
    po && (editSupplier !== po.supplier || editBranch !== po.branch || editNotes !== po.notes)

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
      setLineActionWarning("")
      const result = await addLine.mutateAsync({
        poId: po.id,
        data: {
          item: payload.itemId,
          ordered_quantity: payload.ordered_quantity,
          unit_price: payload.unit_price,
        },
      })
      if (result.warnings?.length) {
        setLineActionWarning(result.warnings.join(" "))
      }
    } catch {
      setLineActionError("Failed to add the new line.")
    }
  }

  async function handleDownloadPdf() {
    if (!po || pdfStatus === "loading") return
    setPdfStatus("loading")
    setPdfError(null)
    const result = await downloadPdf(`orgs/${orgId}/purchase-orders/${po.id}/export/pdf/`)
    if (result.ok) {
      setPdfStatus("success")
      setTimeout(() => setPdfStatus("idle"), 1500)
    } else {
      setPdfError(result.error ?? "Download failed.")
      setPdfStatus("error")
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
            {isDraft && canAccess(["OWNER", "ADMIN"]) ? (
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="edit-supplier" className="text-xs text-muted-foreground">Supplier</Label>
                  <select
                    id="edit-supplier"
                    value={editSupplier}
                    onChange={(e) => setEditSupplier(e.target.value)}
                    disabled={isActionPending}
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm outline-none"
                  >
                    <option value="">Select supplier</option>
                    {(suppliersQuery.data ?? []).filter((s) => s.is_active || String(s.id) === editSupplier).map((s) => (
                      <option key={s.id} value={String(s.id)}>{s.display_name}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="edit-branch" className="text-xs text-muted-foreground">Branch</Label>
                  <select
                    id="edit-branch"
                    value={editBranch}
                    onChange={(e) => setEditBranch(e.target.value)}
                    disabled={isActionPending}
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm outline-none"
                  >
                    <option value="">Select branch</option>
                    {(branchesQuery.data ?? []).map((b) => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1 md:col-span-2">
                  <Label htmlFor="edit-notes" className="text-xs text-muted-foreground">Notes</Label>
                  <Textarea
                    id="edit-notes"
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                    disabled={isActionPending}
                    rows={2}
                  />
                </div>
                {headerChanged ? (
                  <div className="md:col-span-2 flex items-center gap-3">
                    <Button size="sm" onClick={() => void handleSaveHeader()} disabled={isActionPending}>
                      Save changes
                    </Button>
                    {headerError ? <p className="text-sm text-red-600">{headerError}</p> : null}
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="grid gap-2 text-sm text-muted-foreground">
                <p>Supplier: {supplierMap.get(String(po.supplier)) ?? "—"}</p>
                <p>Branch: {branchMap.get(po.branch) ?? "—"}</p>
                <p>Created by: {po.created_by_display ?? "—"}</p>
                <p>Created at: {new Date(po.created_at).toLocaleString()}</p>
              </div>
            )}
          </div>
          <div className="flex flex-col items-start gap-3 md:items-end">
            <POStatusBadge status={po.status} />
            <div className="text-right">
              <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Total value</p>
              <p className="text-2xl font-semibold">{formatPOValue(calculatePOTotal(po.lines))}</p>
            </div>
            <div className="flex flex-col items-end gap-2">
              <div className="flex gap-3">
                {po.status === "DRAFT" ? (
                  <>
                    <Button disabled={isActionPending} onClick={() => setSubmitDialogOpen(true)}>
                      Submit
                    </Button>
                    {canAccess(["OWNER"]) ? (
                      <Button variant="ghost" disabled={isActionPending} onClick={() => setCancelDialogOpen(true)}>
                        Cancel
                      </Button>
                    ) : null}
                  </>
                ) : null}
                {po.status === "SUBMITTED" && canAccess(["OWNER"]) ? (
                  <Button variant="ghost" disabled={isActionPending} onClick={() => setCancelDialogOpen(true)}>
                    Cancel
                  </Button>
                ) : null}
                <Button
                  variant="outline"
                  size="sm"
                  disabled={pdfStatus === "loading"}
                  onClick={() => void handleDownloadPdf()}
                >
                  {pdfStatus === "loading" ? "Generating…" : pdfStatus === "success" ? "Downloaded!" : "Download PDF"}
                </Button>
              </div>
              {pdfStatus === "error" && pdfError
                ? <p className="text-sm text-destructive">{pdfError}</p>
                : null}
            </div>
          </div>
        </CardHeader>
      </Card>

      {!isDraft && po.notes ? (
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
          {lineActionWarning ? <p className="text-sm text-amber-600">{lineActionWarning}</p> : null}
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
          supplierId={po.supplier}
          existingItemIds={po.lines.map((line) => line.item.id)}
          onAddLine={(payload) => void handleAddLine(payload)}
          disabled={isActionPending}
        />
      ) : null}

      <ConfirmDialog
        open={submitDialogOpen}
        onOpenChange={(open) => {
          setSubmitDialogOpen(open)
          if (!open) setSubmitError("")
        }}
        title="Submit Purchase Order"
        description="Once submitted this order cannot be edited. Are you sure?"
        confirmLabel="Submit"
        onConfirm={async () => {
          setSubmitError("")
          try {
            await submitPO.mutateAsync(po.id)
            setSubmitDialogOpen(false)
          } catch {
            setSubmitError("Failed to submit. Please try again.")
          }
        }}
        error={submitError}
      />

      <ConfirmDialog
        open={cancelDialogOpen}
        onOpenChange={(open) => {
          setCancelDialogOpen(open)
          if (!open) setCancelError("")
        }}
        title="Cancel Purchase Order"
        description="This will cancel the purchase order. This cannot be undone."
        confirmLabel="Cancel Order"
        onConfirm={async () => {
          setCancelError("")
          try {
            await cancelPO.mutateAsync(po.id)
            setCancelDialogOpen(false)
          } catch {
            setCancelError("Failed to cancel. Please try again.")
          }
        }}
        error={cancelError}
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
