"use client"

import { useEffect, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
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
import { usePOBranches } from "@/lib/hooks/purchase-orders/usePOBranches"
import { useSlowDeadStock } from "@/lib/hooks/reports/useSlowDeadStock"
import { useOrg } from "@/lib/hooks/useOrg"
import type { SlowDeadStockRow } from "@/lib/types/reports"

type StatusFilter = "all" | "slow" | "dead"

function formatValuation(value: string | null): string {
  if (value === null) return "—"
  return parseFloat(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatCost(value: string | null): string {
  if (value === null) return "—"
  return parseFloat(value).toFixed(2)
}

function formatDate(isoString: string | null): string {
  if (!isoString) return "—"
  return new Date(isoString).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  })
}

function StatusBadge({ status }: { status: "SLOW" | "DEAD" }) {
  return (
    <Badge variant={status === "DEAD" ? "destructive" : "secondary"}>
      {status === "DEAD" ? "Dead" : "Slow"}
    </Badge>
  )
}

function exportCSV(data: SlowDeadStockRow[], filename: string) {
  const escape = (v: string) => (v.includes(",") ? `"${v}"` : v)
  const headers = [
    "Item",
    "SKU",
    "Branch",
    "Qty",
    "Status",
    "Inactive Days",
    "Last Outbound",
    "Latest Cost",
    "Latest Value",
  ]
  const rows = data.map((row) => [
    escape(row.item_name),
    escape(row.item_sku),
    escape(row.branch_name),
    row.quantity_on_hand,
    row.status,
    String(row.inactive_days),
    row.last_outbound_at ? new Date(row.last_outbound_at).toISOString() : "",
    row.latest_unit_cost ?? "",
    row.latest_valuation ?? "",
  ])
  const csv = [headers, ...rows].map((r) => r.join(",")).join("\n")
  const blob = new Blob([csv], { type: "text/csv" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function SlowDeadStockPage() {
  const { orgId, canAccess } = useOrg()
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  const canView = canAccess(["OWNER", "ADMIN"])

  const branch = searchParams.get("branch") ?? ""
  const search = searchParams.get("search") ?? ""
  const statusParam = (searchParams.get("status") ?? "all") as StatusFilter
  const page = Number.parseInt(searchParams.get("page") ?? "1", 10) || 1

  const [searchDraft, setSearchDraft] = useState(search)

  useEffect(() => {
    setSearchDraft(search)
  }, [search])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const trimmed = searchDraft.trim()
      const params = new URLSearchParams(searchParams.toString())
      if (trimmed.length >= 2) {
        params.set("search", trimmed)
      } else {
        params.delete("search")
      }
      params.set("page", "1")
      const qs = params.toString()
      router.replace(qs ? `${pathname}?${qs}` : pathname)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [searchDraft, pathname, router, searchParams])

  function updateParam(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString())
    if (value) params.set(key, value)
    else params.delete(key)
    if (key !== "page") params.set("page", "1")
    const qs = params.toString()
    router.replace(qs ? `${pathname}?${qs}` : pathname)
  }

  const branchesQuery = usePOBranches(canView ? orgId : "")

  const reportQuery = useSlowDeadStock({
    orgId: canView ? orgId : "",
    branch: branch || undefined,
    search: search || undefined,
    status: statusParam,
    page,
  })

  if (!canView) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view slow/dead stock reports in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  const reportErrorMessage =
    reportQuery.error instanceof Error ? reportQuery.error.message : ""

  if (reportErrorMessage.includes("403")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view slow/dead stock reports in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (reportQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load slow/dead stock</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {reportErrorMessage ||
              "There was a problem loading slow/dead stock data. Try again."}
          </p>
          <Button onClick={() => void reportQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const summary = reportQuery.data?.summary
  const results = reportQuery.data?.results ?? []
  const count = reportQuery.data?.count ?? 0
  const pageSize = 50
  const firstRow = count === 0 ? 0 : (page - 1) * pageSize + 1
  const lastRow = count === 0 ? 0 : Math.min((page - 1) * pageSize + results.length, count)

  const csvFilename = `slow-dead-stock-${new Date().toISOString().slice(0, 10)}.csv`

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Slow / Dead Stock</h1>
        <p className="text-sm text-muted-foreground">
          Items with no outbound movement for 90+ days. Slow = 90–179 days inactive. Dead = 180+ days.
        </p>
      </div>

      {/* Filter bar */}
      <div className="grid gap-4 rounded-xl border border-border bg-card p-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,14rem),1fr))]">
        <div className="space-y-2">
          <Label htmlFor="sd-search">Search</Label>
          <Input
            id="sd-search"
            placeholder="Search by item name or SKU"
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="sd-branch">Branch</Label>
          <select
            id="sd-branch"
            value={branch}
            onChange={(e) => updateParam("branch", e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            <option value="">All branches</option>
            {(branchesQuery.data ?? []).map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="sd-status">Status</Label>
          <select
            id="sd-status"
            value={statusParam}
            onChange={(e) => updateParam("status", e.target.value === "all" ? "" : e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            <option value="all">All (slow + dead)</option>
            <option value="slow">Slow only (90–179 days)</option>
            <option value="dead">Dead only (180+ days)</option>
          </select>
        </div>
      </div>

      {/* Summary cards */}
      {reportQuery.isLoading ? (
        <SlowDeadSkeleton />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <SummaryCard
              title="Slow Items"
              value={summary ? String(summary.slow_count) : "—"}
            />
            <SummaryCard
              title="Dead Items"
              value={summary ? String(summary.dead_count) : "—"}
            />
            <SummaryCard
              title="Slow Stock Value"
              value={summary ? formatValuation(summary.total_slow_valuation) : "—"}
            />
            <SummaryCard
              title="Dead Stock Value"
              value={summary ? formatValuation(summary.total_dead_valuation) : "—"}
            />
          </div>

          {/* Results table */}
          <Card>
            <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="space-y-1">
                <CardTitle>Stagnant Stock</CardTitle>
                <p className="text-sm text-muted-foreground">
                  {count > 0
                    ? `Showing ${firstRow}–${lastRow} of ${count} item${count === 1 ? "" : "s"}.`
                    : "No items found for the current filter."}
                </p>
              </div>
              {results.length > 0 && (
                <Button onClick={() => exportCSV(results, csvFilename)}>Export CSV</Button>
              )}
            </CardHeader>
            <CardContent className="p-0">
              {results.length === 0 ? (
                <p className="p-8 text-center text-sm text-muted-foreground">
                  No slow or dead stock found
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Item</TableHead>
                      <TableHead>SKU</TableHead>
                      <TableHead>Branch</TableHead>
                      <TableHead className="text-right">Qty</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Inactive Days</TableHead>
                      <TableHead>Last Outbound</TableHead>
                      <TableHead className="text-right">Latest Value</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {results.map((row) => (
                      <TableRow key={`${row.item_id}-${row.branch_id}`}>
                        <TableCell>{row.item_name}</TableCell>
                        <TableCell className="font-mono text-xs">{row.item_sku}</TableCell>
                        <TableCell>{row.branch_name}</TableCell>
                        <TableCell className="text-right">
                          {parseFloat(row.quantity_on_hand).toLocaleString()}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={row.status} />
                        </TableCell>
                        <TableCell className="text-right">{row.inactive_days}</TableCell>
                        <TableCell>{formatDate(row.last_outbound_at)}</TableCell>
                        <TableCell className="text-right">
                          {formatCost(row.latest_valuation)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Pagination */}
          <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              {reportQuery.isFetching
                ? "Updating..."
                : count > 0
                  ? `Showing ${firstRow}–${lastRow} of ${count}`
                  : "No rows"}
            </p>
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                disabled={page <= 1 || reportQuery.isFetching}
                onClick={() => updateParam("page", String(Math.max(1, page - 1)))}
              >
                Previous
              </Button>
              <span className="text-sm font-medium">Page {page}</span>
              <Button
                variant="ghost"
                disabled={!reportQuery.data?.next || reportQuery.isFetching}
                onClick={() => updateParam("page", String(page + 1))}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function SummaryCard({ title, value }: { title: string; value: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold">{value}</p>
      </CardContent>
    </Card>
  )
}

function SlowDeadSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
      <Skeleton className="h-[28rem] w-full" />
    </div>
  )
}
