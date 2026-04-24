"use client"

import { useEffect, useMemo, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

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
import { useClosePeriods } from "@/lib/hooks/close-periods/useClosePeriods"
import { usePOBranches } from "@/lib/hooks/purchase-orders/usePOBranches"
import { useStockValuation } from "@/lib/hooks/reports/useStockValuation"
import { useOrg } from "@/lib/hooks/useOrg"
import type { StockValuationRow } from "@/lib/types/reports"

function formatValuation(value: string | null): string {
  if (value === null) return "\u2014"
  return parseFloat(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatCost(value: string | null): string {
  if (value === null) return "\u2014"
  return parseFloat(value).toFixed(2)
}

function formatPeriodDate(dateStr: string): string {
  const [year, month, day] = dateStr.split("-").map(Number)
  return new Date(year, month - 1, day).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  })
}

function formatPeriodLabel(start: string, end: string): string {
  return `${formatPeriodDate(start)} – ${formatPeriodDate(end)}`
}

function formatDateTime(isoString: string | null): string {
  if (!isoString) return "—"
  return new Date(isoString).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function exportCSV(data: StockValuationRow[], filename: string) {
  const escape = (v: string) => (v.includes(",") ? `"${v}"` : v)
  const headers = [
    "Item",
    "SKU",
    "Branch",
    "Qty",
    "Latest Cost",
    "Latest Value",
    "Avg Cost",
    "Avg Value",
  ]
  const rows = data.map((row) => [
    escape(row.item_name),
    escape(row.item_sku),
    escape(row.branch_name),
    row.quantity_on_hand,
    row.latest_unit_cost ?? "",
    row.latest_valuation ?? "",
    row.average_unit_cost ?? "",
    row.average_valuation ?? "",
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

export default function StockValuationPage() {
  const { orgId, canAccess } = useOrg()
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  const canView = canAccess(["OWNER", "ADMIN"])

  const branch = searchParams.get("branch") ?? ""
  const search = searchParams.get("search") ?? ""
  const periodId = searchParams.get("period_id") ?? ""

  const [searchDraft, setSearchDraft] = useState(search)

  // Sync draft when URL search param changes externally
  useEffect(() => {
    setSearchDraft(search)
  }, [search])

  // Debounced search: update URL after 300ms
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const trimmed = searchDraft.trim()
      const params = new URLSearchParams(searchParams.toString())
      if (trimmed.length >= 2) {
        params.set("search", trimmed)
      } else {
        params.delete("search")
      }
      const qs = params.toString()
      router.replace(qs ? `${pathname}?${qs}` : pathname)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [searchDraft, pathname, router, searchParams])

  function updateParam(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString())
    if (value) params.set(key, value)
    else params.delete(key)
    const qs = params.toString()
    router.replace(qs ? `${pathname}?${qs}` : pathname)
  }

  const branchesQuery = usePOBranches(canView ? orgId : "")
  const periodsQuery = useClosePeriods({ orgId: canView ? orgId : "" })

  const closedPeriods = useMemo(
    () => (periodsQuery.data ?? []).filter((p) => p.status === "CLOSED"),
    [periodsQuery.data],
  )

  const selectedPeriod = useMemo(
    () => closedPeriods.find((p) => p.id === periodId) ?? null,
    [closedPeriods, periodId],
  )

  const reportQuery = useStockValuation({
    orgId: canView ? orgId : "",
    branch: branch || undefined,
    search: search || undefined,
    periodId: periodId || undefined,
  })

  if (!canView) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view stock valuation reports in this organisation.
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
            You do not have permission to view stock valuation reports in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (reportQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load stock valuation</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {reportErrorMessage || "There was a problem loading stock valuation data. Try again."}
          </p>
          <Button onClick={() => void reportQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const summary = reportQuery.data?.summary
  const results = reportQuery.data?.results ?? []

  const csvFilename = selectedPeriod
    ? `stock-valuation-${selectedPeriod.start_date}-to-${selectedPeriod.end_date}.csv`
    : `stock-valuation-${new Date().toISOString().slice(0, 10)}.csv`

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Stock Valuation</h1>
        <p className="text-sm text-muted-foreground">
          {selectedPeriod
            ? `Snapshot for ${formatPeriodLabel(selectedPeriod.start_date, selectedPeriod.end_date)}.`
            : "View the current on-hand stock value per item and branch using latest and average costs."}
        </p>
      </div>

      {/* Filter bar */}
      <div className="grid gap-4 rounded-xl border border-border bg-card p-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,14rem),1fr))]">
        <div className="space-y-2">
          <Label htmlFor="sv-search">Search</Label>
          <Input
            id="sv-search"
            placeholder="Search by item name or SKU"
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="sv-branch">Branch</Label>
          <select
            id="sv-branch"
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
          <Label htmlFor="sv-period">Period</Label>
          <select
            id="sv-period"
            value={periodId}
            onChange={(e) => updateParam("period_id", e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            <option value="">Live (current stock)</option>
            {closedPeriods.map((p) => (
              <option key={p.id} value={p.id}>
                {formatPeriodLabel(p.start_date, p.end_date)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Snapshot info banner */}
      {selectedPeriod ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          Showing authoritative snapshot for{" "}
          <strong>
            {formatPeriodLabel(selectedPeriod.start_date, selectedPeriod.end_date)}
          </strong>
          . Closed on {formatDateTime(selectedPeriod.closed_at)} by{" "}
          {selectedPeriod.closed_by?.username ?? "—"}.
        </div>
      ) : null}

      {/* Summary cards */}
      {reportQuery.isLoading ? (
        <StockValuationSkeleton />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <SummaryCard
              title="Total Value (Latest Cost)"
              value={summary ? formatValuation(summary.total_latest_valuation) : "\u2014"}
            />
            <SummaryCard
              title="Total Value (Avg Cost)"
              value={summary ? formatValuation(summary.total_average_valuation) : "\u2014"}
            />
            <SummaryCard
              title="Items in Stock"
              value={summary ? String(summary.item_count) : "\u2014"}
            />
            <SummaryCard
              title="Branches with Stock"
              value={summary ? String(summary.branch_count) : "\u2014"}
            />
          </div>

          {/* Results table */}
          <Card>
            <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="space-y-1">
                <CardTitle>Stock Valuation</CardTitle>
                <p className="text-sm text-muted-foreground">
                  {results.length} item{results.length === 1 ? "" : "s"} with stock in the current
                  filter.
                </p>
              </div>
              {results.length > 0 && (
                <Button onClick={() => exportCSV(results, csvFilename)}>Export CSV</Button>
              )}
            </CardHeader>
            <CardContent className="p-0">
              {results.length === 0 ? (
                <p className="p-8 text-center text-sm text-muted-foreground">
                  No items with stock found
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Item</TableHead>
                      <TableHead>SKU</TableHead>
                      <TableHead>Branch</TableHead>
                      <TableHead className="text-right">Qty</TableHead>
                      <TableHead className="text-right">Latest Cost</TableHead>
                      <TableHead className="text-right">Latest Value</TableHead>
                      <TableHead className="text-right">Avg Cost</TableHead>
                      <TableHead className="text-right">Avg Value</TableHead>
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
                        <TableCell className="text-right">{formatCost(row.latest_unit_cost)}</TableCell>
                        <TableCell className="text-right">{formatCost(row.latest_valuation)}</TableCell>
                        <TableCell className="text-right">{formatCost(row.average_unit_cost)}</TableCell>
                        <TableCell className="text-right">{formatCost(row.average_valuation)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
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

function StockValuationSkeleton() {
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
