"use client"

import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { GoodsReceiptFilters } from "@/components/goods-receipts/GoodsReceiptFilters"
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
import { useGoodsReceipts } from "@/lib/hooks/goods-receipts/useGoodsReceipts"
import { useGRSuppliers } from "@/lib/hooks/goods-receipts/useGRSuppliers"
import { useOrg } from "@/lib/hooks/useOrg"

export default function GoodsReceiptsPage() {
  const { orgId, canAccess } = useOrg()
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  const receiptType = searchParams.get("receipt_type") ?? ""
  const branch = searchParams.get("branch") ?? ""
  const supplier = searchParams.get("supplier") ?? ""
  const dateAfter = searchParams.get("date_after") ?? ""
  const dateBefore = searchParams.get("date_before") ?? ""
  const page = searchParams.get("page") ?? "1"

  const hasInvalidDateRange = !!dateAfter && !!dateBefore && dateAfter > dateBefore

  const receiptsQuery = useGoodsReceipts({
    orgId: hasInvalidDateRange ? "" : orgId,
    receipt_type: receiptType || undefined,
    branch: branch || undefined,
    supplier: supplier || undefined,
    date_after: dateAfter || undefined,
    date_before: dateBefore || undefined,
    page,
  })
  const branchesQuery = useGRBranches(orgId)
  const suppliersQuery = useGRSuppliers(orgId)

  const branchMap = new Map((branchesQuery.data ?? []).map((item) => [item.id, item.name]))
  const supplierMap = new Map((suppliersQuery.data ?? []).map((item) => [item.id, item.name]))
  const errorMessage = receiptsQuery.error instanceof Error ? receiptsQuery.error.message : ""
  const currentPage = Number.parseInt(page, 10) || 1

  function navigatePage(nextPage: number) {
    const params = new URLSearchParams(searchParams.toString())
    params.set("page", String(nextPage))
    router.replace(`${pathname}?${params.toString()}`)
  }

  if (receiptsQuery.isLoading) {
    return <ListSkeleton />
  }

  if (errorMessage.includes("403")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view goods receipts in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (receiptsQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load goods receipts</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            There was a problem loading goods receipts. Try again.
          </p>
          <Button onClick={() => void receiptsQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const receipts = receiptsQuery.data?.results ?? []
  const count = receiptsQuery.data?.count ?? 0

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Goods Receipts</h1>
          <p className="text-sm text-muted-foreground">Track received stock for this organisation.</p>
        </div>
        {canAccess(["OWNER", "ADMIN", "STAFF"]) ? (
          <Link
            href={`/orgs/${orgId}/goods-receipts/new`}
            className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
          >
            New Goods Receipt
          </Link>
        ) : null}
      </div>

      <GoodsReceiptFilters
        branches={branchesQuery.data ?? []}
        suppliers={suppliersQuery.data ?? []}
      />

      <Card>
        <CardContent className="p-0">
          {receipts.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No goods receipts found for the current filters.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Branch</TableHead>
                  <TableHead>Supplier</TableHead>
                  <TableHead>Source Ref</TableHead>
                  <TableHead>Lines</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {receipts.map((receipt) => (
                  <TableRow
                    key={receipt.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => router.push(`/orgs/${orgId}/goods-receipts/${receipt.id}`)}
                  >
                    <TableCell>{new Date(receipt.received_at).toLocaleDateString()}</TableCell>
                    <TableCell>
                      <GoodsReceiptTypeBadge type={receipt.receipt_type} />
                    </TableCell>
                    <TableCell>{branchMap.get(receipt.branch) ?? "—"}</TableCell>
                    <TableCell>{receipt.supplier ? (supplierMap.get(receipt.supplier) ?? "—") : "—"}</TableCell>
                    <TableCell>{receipt.source_reference.trim() || "—"}</TableCell>
                    <TableCell>{receipt.lines.length}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">Total goods receipts: {count}</p>
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            disabled={currentPage <= 1}
            onClick={() => navigatePage(Math.max(1, currentPage - 1))}
          >
            Previous
          </Button>
          <span className="text-sm font-medium">Page {currentPage}</span>
          <Button
            variant="ghost"
            disabled={!receiptsQuery.data?.next}
            onClick={() => navigatePage(currentPage + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}

function ListSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
