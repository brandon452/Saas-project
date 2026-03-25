"use client"

import Link from "next/link"
import { useParams } from "next/navigation"

import { GoodsReceiptTypeBadge } from "@/components/goods-receipts/GoodsReceiptTypeBadge"
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
import { useGRBranches } from "@/lib/hooks/goods-receipts/useGRBranches"
import { useGoodsReceipt } from "@/lib/hooks/goods-receipts/useGoodsReceipt"
import { useGRSuppliers } from "@/lib/hooks/goods-receipts/useGRSuppliers"
import { useOrg } from "@/lib/hooks/useOrg"

function truncateUuid(value: string | null | undefined) {
  if (!value) return "—"
  return `${value.slice(0, 8)}...`
}

export default function GoodsReceiptDetailPage() {
  const params = useParams<{ orgId: string; id: string }>()
  const { orgId } = useOrg()
  const receiptId = params?.id ?? ""

  const receiptQuery = useGoodsReceipt(orgId, receiptId)
  const branchesQuery = useGRBranches(orgId)
  const suppliersQuery = useGRSuppliers(orgId)

  const branchMap = new Map((branchesQuery.data ?? []).map((item) => [item.id, item.name]))
  const supplierMap = new Map((suppliersQuery.data ?? []).map((item) => [item.id, item.name]))
  const errorMessage = receiptQuery.error instanceof Error ? receiptQuery.error.message : ""

  if (receiptQuery.isLoading) {
    return <DetailSkeleton />
  }

  if (errorMessage.includes("404")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Goods receipt not found</CardTitle>
        </CardHeader>
        <CardContent>
          <Link href={`/orgs/${orgId}/goods-receipts`} className="text-sm text-primary">
            Back to goods receipts
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
          <Link href={`/orgs/${orgId}/goods-receipts`} className="text-sm text-primary">
            Back to goods receipts
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (!receiptQuery.data || receiptQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load goods receipt</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">Try loading the page again.</p>
          <Button onClick={() => void receiptQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const receipt = receiptQuery.data

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="space-y-2">
          <div className="text-sm text-muted-foreground">
            <Link href={`/orgs/${orgId}/goods-receipts`} className="hover:text-foreground">
              Goods Receipts
            </Link>{" "}
            / {truncateUuid(receipt.id)}
          </div>
          <GoodsReceiptTypeBadge type={receipt.receipt_type} />
        </div>
        <Link
          href={`/orgs/${orgId}/goods-receipts`}
          className="inline-flex h-10 items-center justify-center rounded-md px-4 text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          Back
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Receipt details</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm text-muted-foreground md:grid-cols-2">
          <p>Date: {new Date(receipt.received_at).toLocaleString()}</p>
          <p>Branch: {branchMap.get(receipt.branch) ?? "—"}</p>
          <p>Supplier: {receipt.supplier ? (supplierMap.get(receipt.supplier) ?? "—") : "—"}</p>
          {receipt.receipt_type === "DIRECT_RECEIPT" ? (
            <p>Source reference: {receipt.source_reference.trim() || "—"}</p>
          ) : (
            <p>
              Purchase order:{" "}
              {receipt.purchase_order ? (
                <Link
                  href={`/orgs/${orgId}/purchase-orders/${receipt.purchase_order}`}
                  className="text-primary hover:underline"
                >
                  {truncateUuid(receipt.purchase_order)}
                </Link>
              ) : (
                "—"
              )}
            </p>
          )}
          {receipt.notes.trim() ? <p className="md:col-span-2">Notes: {receipt.notes}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Lines</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                {receipt.receipt_type === "PO_RECEIPT" ? <TableHead>PO Line</TableHead> : null}
                <TableHead>Item</TableHead>
                <TableHead>Qty Received</TableHead>
                <TableHead>Unit Cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {receipt.lines.map((line) => (
                <TableRow key={line.id}>
                  {receipt.receipt_type === "PO_RECEIPT" ? (
                    <TableCell className="font-mono text-sm">{truncateUuid(line.po_line)}</TableCell>
                  ) : null}
                  <TableCell>{line.item?.name ?? "—"}</TableCell>
                  <TableCell>{line.quantity_received}</TableCell>
                  <TableCell>{line.unit_cost ?? "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
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
