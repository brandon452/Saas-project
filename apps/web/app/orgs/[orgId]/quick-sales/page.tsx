"use client"

import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { QuickSaleStatusBadge } from "@/components/quick-sales/QuickSaleStatusBadge"
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
import { useBranches } from "@/lib/hooks/branches/useBranches"
import { useQuickSales } from "@/lib/hooks/quick-sales/useQuickSales"
import { useOrg } from "@/lib/hooks/useOrg"

const STATUS_OPTIONS = ["CONFIRMED", "VOIDED"] as const

function formatCurrency(value: string) {
  return Number.parseFloat(value || "0").toFixed(2)
}

export default function QuickSalesPage() {
  const { orgId, isParentUser } = useOrg()
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  const branch = searchParams.get("branch") ?? ""
  const status = searchParams.get("status") ?? ""
  const fromDate = searchParams.get("from_date") ?? ""
  const toDate = searchParams.get("to_date") ?? ""
  const page = searchParams.get("page") ?? "1"

  const branchesQuery = useBranches(orgId)
  const quickSalesQuery = useQuickSales({
    orgId,
    branch: branch || undefined,
    status: status || undefined,
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
    page,
  })

  const currentPage = Number.parseInt(page, 10) || 1
  const errorMessage = quickSalesQuery.error instanceof Error ? quickSalesQuery.error.message : ""

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

  if (quickSalesQuery.isLoading || branchesQuery.isLoading) {
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
            You do not have permission to view quick sales in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (quickSalesQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load quick sales</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">There was a problem loading quick sales. Try again.</p>
          <Button onClick={() => void quickSalesQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const quickSales = quickSalesQuery.data?.results ?? []
  const count = quickSalesQuery.data?.count ?? 0

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Quick Sales</h1>
          <p className="text-sm text-muted-foreground">
            Record immediate stock sales and view sale history.
          </p>
        </div>
        {!isParentUser ? (
          <Link
            href={`/orgs/${orgId}/quick-sales/new`}
            className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
          >
            New Sale
          </Link>
        ) : null}
      </div>

      <div className="grid gap-4 rounded-xl border border-border bg-card p-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,14rem),1fr))]">
        <div className="space-y-2">
          <label htmlFor="branch" className="text-sm font-medium">
            Branch
          </label>
          <select
            id="branch"
            value={branch}
            onChange={(event) => updateFilter("branch", event.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            <option value="">All branches</option>
            {(branchesQuery.data ?? []).map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <label htmlFor="status" className="text-sm font-medium">
            Status
          </label>
          <select
            id="status"
            value={status}
            onChange={(event) => updateFilter("status", event.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <label htmlFor="from_date" className="text-sm font-medium">
            From date
          </label>
          <input
            id="from_date"
            type="date"
            value={fromDate}
            onChange={(event) => updateFilter("from_date", event.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="to_date" className="text-sm font-medium">
            To date
          </label>
          <input
            id="to_date"
            type="date"
            value={toDate}
            onChange={(event) => updateFilter("to_date", event.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          />
        </div>

        <div className="flex items-end">
          <Button
            variant="outline"
            className="w-full"
            onClick={() => router.replace(`${pathname}?page=1`)}
          >
            Clear filters
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          {quickSales.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No quick sales found for the current filters.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Branch</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Items</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {quickSales.map((sale) => (
                  <TableRow
                    key={sale.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => router.push(`/orgs/${orgId}/quick-sales/${sale.id}`)}
                  >
                    <TableCell>{new Date(sale.occurred_at).toLocaleString()}</TableCell>
                    <TableCell>{sale.branch.name}</TableCell>
                    <TableCell>{sale.customer_name.trim() || "Walk-in"}</TableCell>
                    <TableCell>{sale.lines.length}</TableCell>
                    <TableCell>{formatCurrency(sale.total_value)}</TableCell>
                    <TableCell>
                      <QuickSaleStatusBadge status={sale.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">Total quick sales: {count}</p>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="ghost"
            disabled={currentPage <= 1}
            onClick={() => updateFilter("page", String(Math.max(1, currentPage - 1)))}
          >
            Previous
          </Button>
          <span className="text-sm font-medium">Page {currentPage}</span>
          <Button
            variant="ghost"
            disabled={!quickSalesQuery.data?.next}
            onClick={() => updateFilter("page", String(currentPage + 1))}
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
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
