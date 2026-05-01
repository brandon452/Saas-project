"use client"

import { useEffect, useMemo, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

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
import { useGRItemSearch } from "@/lib/hooks/goods-receipts/useGRItemSearch"
import { useGRSuppliers } from "@/lib/hooks/goods-receipts/useGRSuppliers"
import { useOrgItem } from "@/lib/hooks/org-items/useOrgItem"
import { usePOBranches } from "@/lib/hooks/purchase-orders/usePOBranches"
import { usePurchaseCostTrend } from "@/lib/hooks/reports/usePurchaseCostTrend"
import { useAuth } from "@/lib/hooks/useAuth"
import { useOrg } from "@/lib/hooks/useOrg"
import type { CostTrendPoint } from "@/lib/types/reports"

type ChartMode = "combined" | "by-supplier"

type CombinedChartRow = {
  timestamp: number
  dateLabel: string
  unitCost: number
  rawPoint: CostTrendPoint
}

type SupplierChartRow = {
  timestamp: number
  dateLabel: string
  rawPoint: CostTrendPoint
  quantity_received: number
  supplierLabel: string
} & Record<string, number | string | CostTrendPoint>

const SUPPLIER_COLORS = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c"]

function formatDateParam(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, "0")
  const day = String(value.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function getDefaultDateRange() {
  const today = new Date()
  const from = new Date(today)
  from.setDate(from.getDate() - 365)

  return {
    fromDate: formatDateParam(from),
    toDate: formatDateParam(today),
  }
}

function getReceiptTypeLabel(receiptType: CostTrendPoint["receipt_type"]) {
  return receiptType === "PO_RECEIPT" ? "PO Receipt" : "Direct Receipt"
}

function getSelectedItemLabel(
  itemId: string,
  draft: string,
  results: Array<{ id: string; name: string }>,
): string | null {
  const matched = results.find((result) => result.id === itemId)
  if (matched) return matched.name
  if (draft.trim().length >= 2) return draft.trim()
  return null
}

function exportCSV(data: CostTrendPoint[], itemName: string) {
  const escape = (value: string) => (value.includes(",") ? `"${value}"` : value)

  const headers = [
    "Date",
    "Supplier",
    "Branch",
    "Unit Cost",
    "Qty Received",
    "Receipt Type",
  ]

  const rows = data.map((point) => [
    escape(new Date(point.date).toLocaleString()),
    escape(point.supplier_name ?? ""),
    escape(point.branch_name),
    escape(point.unit_cost),
    String(point.quantity_received),
    escape(point.receipt_type),
  ])

  const csv = [headers, ...rows].map((row) => row.join(",")).join("\n")
  const blob = new Blob([csv], { type: "text/csv" })
  const url = URL.createObjectURL(blob)

  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = `cost-trend-${itemName}-${new Date().toISOString().slice(0, 10)}.csv`
  anchor.click()

  URL.revokeObjectURL(url)
}

export default function CostTrendReportPage() {
  const { isLoading: authLoading } = useAuth()
  const { orgId, canAccess } = useOrg()
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  const [itemSearchDraft, setItemSearchDraft] = useState("")
  const [debouncedItemSearch, setDebouncedItemSearch] = useState("")
  const [chartMode, setChartMode] = useState<ChartMode>("combined")

  const canView = canAccess(["OWNER", "ADMIN"])
  const scopedOrgId = canView ? orgId : ""

  const item = searchParams.get("item") ?? ""
  const fromDate = searchParams.get("from_date") ?? ""
  const toDate = searchParams.get("to_date") ?? ""
  const supplier = searchParams.get("supplier") ?? ""
  const branch = searchParams.get("branch") ?? ""

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedItemSearch(itemSearchDraft.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [itemSearchDraft])

  useEffect(() => {
    if (!orgId) return
    if (searchParams.has("from_date") && searchParams.has("to_date")) return

    const defaults = getDefaultDateRange()
    const params = new URLSearchParams(searchParams.toString())
    params.set("from_date", defaults.fromDate)
    params.set("to_date", defaults.toDate)

    const query = params.toString()
    router.replace(query ? `${pathname}?${query}` : pathname)
  }, [orgId, pathname, router, searchParams])

  const hasInvalidDateRange = !!fromDate && !!toDate && fromDate > toDate

  const itemSearchQuery = useGRItemSearch(scopedOrgId, debouncedItemSearch)
  const selectedItemQuery = useOrgItem(canView ? scopedOrgId : "", item)
  const suppliersQuery = useGRSuppliers(scopedOrgId)
  const branchesQuery = usePOBranches(scopedOrgId)
  const reportQuery = usePurchaseCostTrend({
    orgId: canView && !hasInvalidDateRange ? orgId : "",
    item: canView ? item : "",
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
    supplier: supplier || undefined,
    branch: branch || undefined,
  })

  const itemResults = itemSearchQuery.data?.results ?? []
  const reportData = useMemo(() => reportQuery.data?.results ?? [], [reportQuery.data])
  const selectedItemLabel = item
    ? (getSelectedItemLabel(item, itemSearchDraft, itemResults) ??
      selectedItemQuery.data?.name ??
      item)
    : ""

  const supplierSeries = useMemo(() => {
    const seen = new Map<string, string>()

    for (const point of reportData) {
      const supplierKey = point.supplier_id ?? "unknown"
      if (!seen.has(supplierKey)) {
        seen.set(supplierKey, point.supplier_name ?? "Unknown")
      }
    }

    return Array.from(seen.entries()).map(([id, label]) => ({ id, label }))
  }, [reportData])

  const combinedChartData = useMemo<CombinedChartRow[]>(
    () =>
      reportData.map((point) => ({
        timestamp: new Date(point.date).getTime(),
        dateLabel: new Date(point.date).toLocaleDateString(),
        unitCost: Number.parseFloat(point.unit_cost),
        rawPoint: point,
      })),
    [reportData],
  )

  const supplierChartData = useMemo<SupplierChartRow[]>(
    () =>
      reportData.map((point) => {
        const supplierKey = point.supplier_id ?? "unknown"
        return {
          timestamp: new Date(point.date).getTime(),
          dateLabel: new Date(point.date).toLocaleDateString(),
          rawPoint: point,
          quantity_received: point.quantity_received,
          supplierLabel: point.supplier_name ?? "Unknown",
          [`cost__${supplierKey}`]: Number.parseFloat(point.unit_cost),
        }
      }),
    [reportData],
  )

  const filterErrorMessage = useMemo(() => {
    const queries = [suppliersQuery, branchesQuery]
    const failed = queries.find((query) => query.error instanceof Error)
    return failed?.error instanceof Error ? failed.error.message : ""
  }, [branchesQuery, suppliersQuery])

  const reportErrorMessage = reportQuery.error instanceof Error ? reportQuery.error.message : ""

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
    setChartMode("combined")
    replaceParams({ [key]: value || null })
  }

  function handleSelectItem(nextItem: { id: string; name: string }) {
    setChartMode("combined")
    setItemSearchDraft(nextItem.name)
    replaceParams({ item: nextItem.id })
  }

  function handleClearItem() {
    setChartMode("combined")
    setItemSearchDraft("")
    setDebouncedItemSearch("")
    replaceParams({ item: null })
  }

  const itemSearchHelperText =
    debouncedItemSearch.length < 2
      ? "Type at least 2 characters"
      : itemSearchQuery.isFetching
        ? "Loading..."
        : itemResults.length === 0
          ? "No results found"
          : ""

  if (authLoading || (canView && (branchesQuery.isLoading || suppliersQuery.isLoading))) {
    return <CostTrendPageSkeleton />
  }

  if (!canView) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view cost trend reports in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (filterErrorMessage.includes("403") || reportErrorMessage.includes("403")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view cost trend reports in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (filterErrorMessage) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load report filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            There was a problem loading branches or suppliers. Try again.
          </p>
          <Button
            onClick={() => {
              void branchesQuery.refetch()
              void suppliersQuery.refetch()
            }}
          >
            Retry
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (reportQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load purchase cost trend</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            There was a problem loading purchase cost trend data. Try again.
          </p>
          <Button onClick={() => void reportQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Purchase Cost Trend</h1>
        <p className="text-sm text-muted-foreground">
          Compare received unit costs over time for a single item across purchase orders and direct
          receipts.
        </p>
      </div>

      <div className="grid gap-4 rounded-xl border border-border bg-card p-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,14rem),1fr))]">
        <div className="min-w-0 space-y-2">
          <Label htmlFor="cost-trend-item-search">Item</Label>
          <Input
            id="cost-trend-item-search"
            placeholder="Search by item name or SKU"
            value={itemSearchDraft}
            onChange={(event) => setItemSearchDraft(event.target.value)}
          />
          {item ? (
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="max-w-full truncate px-3 py-1 text-sm">
                {selectedItemLabel}
              </Badge>
              <Button variant="ghost" className="h-auto px-2 py-1 text-sm" onClick={handleClearItem}>
                Clear
              </Button>
            </div>
          ) : null}
          <div className="rounded-md border border-border bg-background">
            {itemSearchHelperText ? (
              <p className="px-3 py-2 text-sm text-muted-foreground">{itemSearchHelperText}</p>
            ) : (
              itemResults.map((result) => (
                <button
                  key={result.id}
                  type="button"
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-accent"
                  onClick={() => handleSelectItem({ id: result.id, name: result.name })}
                >
                  <span>{result.name}</span>
                  <span className="text-muted-foreground">{result.sku}</span>
                </button>
              ))
            )}
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="cost-trend-from-date">From date</Label>
          <Input
            id="cost-trend-from-date"
            type="date"
            value={fromDate}
            onChange={(event) => updateFilter("from_date", event.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="cost-trend-to-date">To date</Label>
          <Input
            id="cost-trend-to-date"
            type="date"
            value={toDate}
            onChange={(event) => updateFilter("to_date", event.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="cost-trend-supplier">Supplier</Label>
          <select
            id="cost-trend-supplier"
            value={supplier}
            onChange={(event) => updateFilter("supplier", event.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            <option value="">All suppliers</option>
            {(suppliersQuery.data ?? []).map((option) => (
              <option key={option.id} value={String(option.id)}>
                {option.display_name}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="cost-trend-branch">Branch</Label>
          <select
            id="cost-trend-branch"
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

        {hasInvalidDateRange ? (
          <div className="col-span-full">
            <p className="text-sm text-red-600">From date must be on or before to date.</p>
          </div>
        ) : null}
      </div>

      {!item ? (
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            Select an item to view its purchase cost trend
          </CardContent>
        </Card>
      ) : hasInvalidDateRange ? (
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            Fix the date range to load purchase cost trend data.
          </CardContent>
        </Card>
      ) : reportQuery.isLoading ? (
        <CostTrendResultsSkeleton />
      ) : reportData.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            No purchase history found for this item in the selected date range
          </CardContent>
        </Card>
      ) : (
        <>
          {reportQuery.data?.truncated ? (
            <div className="rounded-md border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
              Showing the first {reportQuery.data.limit.toLocaleString()} of{" "}
              {reportQuery.data.total_count.toLocaleString()} receipt points. Narrow the date
              range or apply a supplier/branch filter to see all data.
            </div>
          ) : null}

          <Card>
            <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="space-y-1">
                <CardTitle>Trend Chart</CardTitle>
                <p className="text-sm text-muted-foreground">
                  {reportQuery.data?.truncated
                    ? `Showing ${reportData.length} of ${(reportQuery.data.total_count).toLocaleString()} receipt points.`
                    : `${reportData.length} receipt point${reportData.length === 1 ? "" : "s"} in the current filter window.`}
                </p>
              </div>
              <div className="inline-flex rounded-md border border-border bg-muted p-1">
                <Button
                  variant={chartMode === "combined" ? "default" : "ghost"}
                  className="px-3 py-1.5"
                  onClick={() => setChartMode("combined")}
                >
                  Combined
                </Button>
                <Button
                  variant={chartMode === "by-supplier" ? "default" : "ghost"}
                  className="px-3 py-1.5"
                  onClick={() => setChartMode("by-supplier")}
                >
                  By Supplier
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="h-[360px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  {chartMode === "combined" ? (
                    <LineChart data={combinedChartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="timestamp"
                        type="number"
                        scale="time"
                        domain={["dataMin", "dataMax"]}
                        tickFormatter={(value) => new Date(value).toLocaleDateString()}
                      />
                      <YAxis tickFormatter={(value) => Number(value).toFixed(2)} />
                      <Tooltip content={<CombinedTooltip />} />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="unitCost"
                        name="Unit Cost"
                        stroke={SUPPLIER_COLORS[0]}
                        strokeWidth={2}
                        dot={{ r: 3 }}
                      />
                    </LineChart>
                  ) : (
                    <LineChart data={supplierChartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="timestamp"
                        type="number"
                        scale="time"
                        domain={["dataMin", "dataMax"]}
                        tickFormatter={(value) => new Date(value).toLocaleDateString()}
                      />
                      <YAxis tickFormatter={(value) => Number(value).toFixed(2)} />
                      <Tooltip content={<SupplierTooltip />} />
                      <Legend />
                      {supplierSeries.map((series, index) => (
                        <Line
                          key={series.id}
                          type="monotone"
                          dataKey={`cost__${series.id}`}
                          name={series.label}
                          stroke={SUPPLIER_COLORS[index % SUPPLIER_COLORS.length]}
                          strokeWidth={2}
                          dot={{ r: 3 }}
                          connectNulls
                        />
                      ))}
                    </LineChart>
                  )}
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="space-y-1">
                <CardTitle>Raw Data</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Export the current filtered dataset or inspect each receipt point below.
                </p>
              </div>
              <Button onClick={() => exportCSV(reportData, selectedItemLabel)}>Export CSV</Button>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Supplier</TableHead>
                    <TableHead>Branch</TableHead>
                    <TableHead>Unit Cost</TableHead>
                    <TableHead>Qty</TableHead>
                    <TableHead>Type</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reportData.map((point) => (
                    <TableRow key={point.receipt_id}>
                      <TableCell>{new Date(point.date).toLocaleString()}</TableCell>
                      <TableCell>{point.supplier_name ?? "\u2014"}</TableCell>
                      <TableCell>{point.branch_name}</TableCell>
                      <TableCell>{Number.parseFloat(point.unit_cost).toFixed(2)}</TableCell>
                      <TableCell>{point.quantity_received}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{getReceiptTypeLabel(point.receipt_type)}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

function CombinedTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: CombinedChartRow }>
}) {
  if (!active || !payload?.length) return null

  const point = payload[0]?.payload.rawPoint
  if (!point) return null

  return (
    <div className="rounded-md border border-border bg-background p-3 text-sm shadow-sm">
      <p>{new Date(point.date).toLocaleString()}</p>
      <p>Unit cost: {Number.parseFloat(point.unit_cost).toFixed(2)}</p>
      <p>Supplier: {point.supplier_name ?? "Unknown"}</p>
      <p>Qty: {point.quantity_received}</p>
    </div>
  )
}

function SupplierTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ dataKey?: string; payload: SupplierChartRow }>
}) {
  if (!active || !payload?.length) return null

  const activePayload = payload.find((entry) => {
    if (!entry?.dataKey) return false
    const value = entry.payload[entry.dataKey]
    return typeof value === "number"
  })

  if (!activePayload) return null

  const point = activePayload.payload.rawPoint
  if (!point) return null

  return (
    <div className="rounded-md border border-border bg-background p-3 text-sm shadow-sm">
      <p>{new Date(point.date).toLocaleString()}</p>
      <p>Unit cost: {Number.parseFloat(point.unit_cost).toFixed(2)}</p>
      <p>Qty: {point.quantity_received}</p>
      <p>Supplier: {point.supplier_name ?? "Unknown"}</p>
    </div>
  )
}

function CostTrendPageSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-56" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}

function CostTrendResultsSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-[28rem] w-full" />
      <Skeleton className="h-[24rem] w-full" />
    </div>
  )
}
