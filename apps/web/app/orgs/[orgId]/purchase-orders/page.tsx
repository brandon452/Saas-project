"use client"

import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { POFilters } from "@/components/purchase-orders/POFilters"
import { POStatusBadge } from "@/components/purchase-orders/POStatusBadge"
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
import { usePurchaseOrders } from "@/lib/hooks/purchase-orders/usePurchaseOrders"
import { usePOSuppliers } from "@/lib/hooks/purchase-orders/usePOSuppliers"
import { useExportCsv } from "@/lib/hooks/useExportCsv"
import { useOrg } from "@/lib/hooks/useOrg"
import { calculatePOTotal, formatPOValue } from "@/lib/utils/po"

export default function PurchaseOrdersPage() {
  const { orgId, canAccess } = useOrg()
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  const page = Number.parseInt(searchParams.get("page") ?? "1", 10) || 1
  const status = searchParams.get("status") ?? ""
  const supplier = searchParams.get("supplier") ?? ""
  const branch = searchParams.get("branch") ?? ""
  const search = searchParams.get("search") ?? ""
  const dateTo = searchParams.get("created_at_before") ?? ""
  const dateFrom = searchParams.get("created_at_after") ?? ""

  const purchaseOrdersQuery = usePurchaseOrders({
    orgId,
    page,
    status: status || undefined,
    supplier: supplier ? Number.parseInt(supplier, 10) : undefined,
    branch: branch ? Number.parseInt(branch, 10) : undefined,
    search: search || undefined,
    dateFrom: dateFrom || undefined,
    dateTo: dateTo || undefined,
  })
  const suppliersQuery = usePOSuppliers(orgId)
  const branchesQuery = usePOBranches(orgId)

  function updateFilter(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString())

    if (value) {
      params.set(key, value)
    } else {
      params.delete(key)
    }

    if (key !== "page") {
      params.set("page", "1")
    }

    router.replace(`${pathname}?${params.toString()}`)
  }

  function navigatePage(nextPage: number) {
    updateFilter("page", String(nextPage))
  }

  const { exportStatus, exportError, triggerExport } = useExportCsv()

  function handleExport() {
    const params = new URLSearchParams()
    if (status) params.set("status", status)
    if (supplier) params.set("supplier", supplier)
    if (branch) params.set("branch", branch)
    if (search) params.set("search", search)
    if (dateFrom) params.set("created_at_after", dateFrom)
    if (dateTo) params.set("created_at_before", dateTo)
    void triggerExport(`orgs/${orgId}/purchase-orders/export/csv/`, params)
  }

  const supplierMap = new Map((suppliersQuery.data ?? []).map((item) => [String(item.id), item.display_name]))
  const branchMap = new Map((branchesQuery.data ?? []).map((item) => [item.id, item.name]))
  const errorMessage = purchaseOrdersQuery.error instanceof Error ? purchaseOrdersQuery.error.message : ""

  if (
    (purchaseOrdersQuery.isLoading && !purchaseOrdersQuery.data) ||
    suppliersQuery.isLoading ||
    branchesQuery.isLoading
  ) {
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
            You do not have permission to view purchase orders in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (purchaseOrdersQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load purchase orders</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            There was a problem loading purchase orders. Try again.
          </p>
          <Button onClick={() => void purchaseOrdersQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const orders = purchaseOrdersQuery.data?.results ?? []
  const count = purchaseOrdersQuery.data?.count ?? 0

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Purchase Orders</h1>
          <p className="text-sm text-muted-foreground">
            View and manage purchase orders for this organisation.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={exportStatus === "loading"}
            onClick={handleExport}
          >
            {exportStatus === "loading" ? "Exporting…" : exportStatus === "success" ? "Exported!" : "Export CSV"}
          </Button>
          {canAccess(["OWNER", "ADMIN"]) ? (
            <Link
              href={`/orgs/${orgId}/purchase-orders/new`}
              className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
            >
              New Purchase Order
            </Link>
          ) : null}
        </div>
      </div>
      {exportStatus === "error" && exportError
        ? <p className="text-sm text-destructive">{exportError}</p>
        : null}

      <POFilters
        status={status}
        supplier={supplier}
        branch={branch}
        search={search}
        dateFrom={dateFrom}
        dateTo={dateTo}
        suppliers={suppliersQuery.data ?? []}
        branches={branchesQuery.data ?? []}
        onFilterChange={updateFilter}
      />

      <Card>
        <CardContent
          aria-busy={purchaseOrdersQuery.isFetching}
          className={["p-0 transition-opacity", purchaseOrdersQuery.isFetching ? "opacity-70" : "opacity-100"].join(" ")}
        >
          {orders.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No purchase orders found for the current filters.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>PO Number</TableHead>
                  <TableHead>Supplier</TableHead>
                  <TableHead>Branch</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Total Value</TableHead>
                  <TableHead>Created At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {orders.map((po) => (
                  <TableRow
                    key={po.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => router.push(`/orgs/${orgId}/purchase-orders/${po.id}`)}
                  >
                    <TableCell className="font-medium">{po.po_number}</TableCell>
                    <TableCell>{supplierMap.get(String(po.supplier)) ?? "—"}</TableCell>
                    <TableCell>{branchMap.get(po.branch) ?? "—"}</TableCell>
                    <TableCell>
                      <POStatusBadge status={po.status} />
                    </TableCell>
                    <TableCell>{formatPOValue(calculatePOTotal(po.lines))}</TableCell>
                    <TableCell>{new Date(po.created_at).toLocaleDateString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          {purchaseOrdersQuery.isFetching ? "Updating purchase orders..." : `Total purchase orders: ${count}`}
        </p>
        <div className="flex items-center gap-3">
          <Button variant="ghost" disabled={page <= 1} onClick={() => navigatePage(page - 1)}>
            Previous
          </Button>
          <span className="text-sm font-medium">Page {page}</span>
          <Button
            variant="ghost"
            disabled={!purchaseOrdersQuery.data?.next}
            onClick={() => navigatePage(page + 1)}
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
