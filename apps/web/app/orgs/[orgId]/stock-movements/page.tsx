"use client"

import { useMemo } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
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
import { useStockMovements } from "@/lib/hooks/stock-movements/useStockMovements"
import { useOrg } from "@/lib/hooks/useOrg"
import type { StockLedgerEntry } from "@/lib/types/stock-adjustments"
import { toRelativePath } from "@/lib/utils/pagination"

function getPageFromNext(next: string | null): string | null {
  if (!next) return null
  const relativePath = toRelativePath(next)
  const [, query = ""] = relativePath.split("?")
  return new URLSearchParams(query).get("page")
}

function getMovementBadgeVariant(movementType: string): "default" | "secondary" | "outline" {
  switch (movementType) {
    case "RECEIPT":
      return "default"
    case "ISSUE":
      return "secondary"
    default:
      return "outline"
  }
}

export default function StockMovementsPage() {
  const { orgId } = useOrg()
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  const branch = searchParams.get("branch") ?? ""
  const item = searchParams.get("item") ?? ""
  const movementType = searchParams.get("movement_type") ?? ""
  const fromDate = searchParams.get("from_date") ?? ""
  const toDate = searchParams.get("to_date") ?? ""
  const ordering = searchParams.get("ordering") ?? "-occurred_at"
  const page = searchParams.get("page") ?? "1"

  const hasInvalidDateRange = !!fromDate && !!toDate && fromDate > toDate

  const stockMovementsQuery = useStockMovements({
    orgId: hasInvalidDateRange ? "" : orgId,
    branch: branch || undefined,
    item: item || undefined,
    movement_type: movementType || undefined,
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
    ordering,
    page,
  })
  const branchesQuery = usePOBranches(orgId)

  const activeFilters = !!branch || !!item || !!movementType || !!fromDate || !!toDate
  const currentPage = Number.parseInt(page, 10) || 1
  const nextPage = getPageFromNext(stockMovementsQuery.data?.next ?? null)
  const rows: StockLedgerEntry[] = stockMovementsQuery.data?.results ?? []
  const count = stockMovementsQuery.data?.count ?? 0

  const branchOptions = useMemo(
    () =>
      (branchesQuery.data ?? []).map((branchOption) => ({
        id: String(branchOption.id),
        name: branchOption.name,
      })),
    [branchesQuery.data],
  )

  function replaceParams(next: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString())

    for (const [key, value] of Object.entries(next)) {
      if (value) {
        params.set(key, value)
      } else {
        params.delete(key)
      }
    }

    const query = params.toString()
    router.replace(query ? `${pathname}?${query}` : pathname)
  }

  function updateFilter(key: string, value: string) {
    replaceParams({
      [key]: value || null,
      page: key === "page" ? value : "1",
    })
  }

  function clearFilters() {
    replaceParams({
      branch: null,
      item: null,
      movement_type: null,
      from_date: null,
      to_date: null,
      ordering: null,
      page: null,
    })
  }

  if (stockMovementsQuery.isLoading || branchesQuery.isLoading) {
    return <StockMovementsSkeleton />
  }

  const errorMessage = stockMovementsQuery.error instanceof Error ? stockMovementsQuery.error.message : ""

  if (errorMessage.includes("403")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view stock movements in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (stockMovementsQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load stock movements</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            There was a problem loading stock movements. Try again.
          </p>
          <Button onClick={() => void stockMovementsQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Stock Movements</h1>
        <p className="text-sm text-muted-foreground">
          Review receipts, issues, and adjustments across branches with movement-level detail.
        </p>
      </div>

      <div className="grid gap-4 rounded-xl border border-border bg-card p-4 md:grid-cols-2 xl:grid-cols-[220px_220px_1fr_180px_180px_180px_auto]">
        <div className="space-y-2">
          <label htmlFor="movement-branch" className="text-sm font-medium">
            Branch
          </label>
          <select
            id="movement-branch"
            value={branch}
            onChange={(event) => updateFilter("branch", event.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            <option value="">All branches</option>
            {branchOptions.map((branchOption) => (
              <option key={branchOption.id} value={branchOption.id}>
                {branchOption.name}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <label htmlFor="movement-type" className="text-sm font-medium">
            Movement type
          </label>
          <select
            id="movement-type"
            value={movementType}
            onChange={(event) => updateFilter("movement_type", event.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            <option value="">All</option>
            <option value="RECEIPT">Receipt</option>
            <option value="ISSUE">Issue</option>
            <option value="ADJUSTMENT">Adjustment</option>
          </select>
        </div>

        <div className="space-y-2">
          <label htmlFor="movement-item" className="text-sm font-medium">
            Item
          </label>
          <Input
            id="movement-item"
            value={item}
            placeholder="Item UUID"
            onChange={(event) => updateFilter("item", event.target.value)}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="movement-from-date" className="text-sm font-medium">
            From date
          </label>
          <Input
            id="movement-from-date"
            type="date"
            value={fromDate}
            onChange={(event) => updateFilter("from_date", event.target.value)}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="movement-to-date" className="text-sm font-medium">
            To date
          </label>
          <Input
            id="movement-to-date"
            type="date"
            value={toDate}
            onChange={(event) => updateFilter("to_date", event.target.value)}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="movement-ordering" className="text-sm font-medium">
            Sort
          </label>
          <select
            id="movement-ordering"
            value={ordering}
            onChange={(event) => updateFilter("ordering", event.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            <option value="-occurred_at">Newest first</option>
            <option value="occurred_at">Oldest first</option>
          </select>
        </div>

        <div className="flex items-end">
          <Button type="button" variant="outline" className="w-full justify-center" onClick={clearFilters}>
            Clear filters
          </Button>
        </div>

        {hasInvalidDateRange ? (
          <div className="md:col-span-2 xl:col-span-7">
            <p className="text-sm text-red-600">From date must be on or before to date.</p>
          </div>
        ) : null}
      </div>

      <Card>
        <CardContent className="p-0">
          {rows.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              {activeFilters ? "No movements match your filters" : "No stock movements recorded yet"}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Branch</TableHead>
                  <TableHead>Item</TableHead>
                  <TableHead>SKU</TableHead>
                  <TableHead>Qty</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>By</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => {
                  const quantityValue = Number(row.quantity)
                  const quantityTone = quantityValue > 0 ? "text-emerald-600" : quantityValue < 0 ? "text-red-600" : ""

                  return (
                    <TableRow key={row.id}>
                      <TableCell>{new Date(row.occurred_at ?? row.created_at).toLocaleString()}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap items-center gap-2">
                          <span>{row.branch.name}</span>
                          <Badge variant="outline">{row.branch.code}</Badge>
                        </div>
                      </TableCell>
                      <TableCell className="font-medium">{row.item.name}</TableCell>
                      <TableCell className="font-mono text-sm">{row.item.sku}</TableCell>
                      <TableCell className={quantityTone}>{row.quantity}</TableCell>
                      <TableCell>
                        <Badge variant={getMovementBadgeVariant(row.movement_type)}>{row.movement_type}</Badge>
                      </TableCell>
                      <TableCell>{row.reason || "\u2014"}</TableCell>
                      <TableCell>{row.performed_by?.username || "\u2014"}</TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">Total stock movements: {count}</p>
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            disabled={currentPage <= 1}
            onClick={() => updateFilter("page", String(Math.max(1, currentPage - 1)))}
          >
            Previous
          </Button>
          <span className="text-sm font-medium">Page {page}</span>
          <Button variant="ghost" disabled={!nextPage} onClick={() => updateFilter("page", nextPage ?? page)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}

function StockMovementsSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-48" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
