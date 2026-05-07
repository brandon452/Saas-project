"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { CreateStockTakeDialog } from "@/components/stock-takes/CreateStockTakeDialog"
import { CycleDuePanel } from "@/components/stock-takes/CycleDuePanel"
import { GenerateCycleCountDialog } from "@/components/stock-takes/GenerateCycleCountDialog"
import { StockTakeStatusBadge } from "@/components/stock-takes/StockTakeStatusBadge"
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
import { useStockTakes } from "@/lib/hooks/stock-takes/useStockTakes"
import { usePOBranches } from "@/lib/hooks/purchase-orders/usePOBranches"
import { useOrg } from "@/lib/hooks/useOrg"
import { formatDateTime, getStockTakeBranchLabel } from "@/lib/utils/stock-takes"
import { toRelativePath } from "@/lib/utils/pagination"

function getPageFromNext(next: string | null): string | null {
  if (!next) return null
  const relativePath = toRelativePath(next)
  const [, query = ""] = relativePath.split("?")
  return new URLSearchParams(query).get("page")
}

export default function StockTakesPage() {
  const { orgId, canAccess } = useOrg()
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [createOpen, setCreateOpen] = useState(false)
  const [generateCycleOpen, setGenerateCycleOpen] = useState(false)

  const page = searchParams.get("page") ?? "1"
  const stockTakeType = searchParams.get("stock_take_type") ?? ""
  const cycleItemClass = searchParams.get("cycle_item_class") ?? ""
  const stockTakesQuery = useStockTakes(orgId, { page, stock_take_type: stockTakeType, cycle_item_class: cycleItemClass })
  const branchesQuery = usePOBranches(orgId)

  const branches = useMemo(
    () =>
      (branchesQuery.data ?? []).map((branch) => ({
        id: String(branch.id),
        name: branch.name,
      })),
    [branchesQuery.data],
  )

  function updatePage(nextPage: string | null) {
    if (!nextPage) return
    const params = new URLSearchParams(searchParams.toString())
    params.set("page", nextPage)
    router.replace(`${pathname}?${params.toString()}`)
  }

  function updateFilter(key: "stock_take_type" | "cycle_item_class", value: string) {
    const params = new URLSearchParams(searchParams.toString())
    if (value) {
      params.set(key, value)
    } else {
      params.delete(key)
    }
    params.set("page", "1")
    router.replace(`${pathname}?${params.toString()}`)
  }

  if (stockTakesQuery.isLoading) {
    return <StockTakeListSkeleton />
  }

  const errorMessage = stockTakesQuery.error instanceof Error ? stockTakesQuery.error.message : ""

  if (errorMessage.includes("403")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view stock takes in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (stockTakesQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load stock takes</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            There was a problem loading stock takes. Try again.
          </p>
          <Button onClick={() => void stockTakesQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const rows = stockTakesQuery.data?.results ?? []
  const count = stockTakesQuery.data?.count ?? 0
  const previousPage = page === "1" ? null : String(Math.max(1, Number.parseInt(page, 10) - 1))
  const nextPage = getPageFromNext(stockTakesQuery.data?.next ?? null)

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Stock Takes</h1>
          <p className="text-sm text-muted-foreground">
            Manage physical stock counts and approval workflows by branch.
          </p>
        </div>
        {canAccess(["OWNER", "ADMIN"]) ? (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setGenerateCycleOpen(true)}>
              Generate Cycle Count
            </Button>
            <Button onClick={() => setCreateOpen(true)}>New Stock Take</Button>
          </div>
        ) : null}
      </div>

      <div className="grid gap-3 rounded-xl border border-border bg-card p-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="text-sm font-medium">Type</label>
          <select
            value={stockTakeType}
            onChange={(event) => updateFilter("stock_take_type", event.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            <option value="">All</option>
            <option value="FULL">Full</option>
            <option value="CYCLE">Cycle</option>
          </select>
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Cycle Class</label>
          <select
            value={cycleItemClass}
            onChange={(event) => updateFilter("cycle_item_class", event.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            <option value="">All</option>
            <option value="A">A</option>
            <option value="B">B</option>
            <option value="C">C</option>
          </select>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          {rows.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">No stock takes found</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Branch</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Class</TableHead>
                  <TableHead>Scheduled</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead>Approved</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((stockTake) => (
                  <TableRow key={stockTake.id}>
                    <TableCell>{getStockTakeBranchLabel(stockTake.branch, branchesQuery.data)}</TableCell>
                    <TableCell>{stockTake.stock_take_type}</TableCell>
                    <TableCell>{stockTake.cycle_item_class ?? "\u2014"}</TableCell>
                    <TableCell>{formatDateTime(stockTake.scheduled_for)}</TableCell>
                    <TableCell>
                      <StockTakeStatusBadge status={stockTake.status} />
                    </TableCell>
                    <TableCell>{formatDateTime(stockTake.created_at)}</TableCell>
                    <TableCell>{formatDateTime(stockTake.started_at)}</TableCell>
                    <TableCell>{formatDateTime(stockTake.submitted_at)}</TableCell>
                    <TableCell>{formatDateTime(stockTake.approved_at)}</TableCell>
                    <TableCell>
                      <Link
                        href={`/orgs/${orgId}/stock-takes/${stockTake.id}`}
                        className="text-sm font-medium text-primary"
                      >
                        View
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">Total stock takes: {count}</p>
        <div className="flex items-center gap-3">
          <Button variant="ghost" disabled={!previousPage} onClick={() => updatePage(previousPage)}>
            Previous
          </Button>
          <span className="text-sm font-medium">Page {page}</span>
          <Button variant="ghost" disabled={!nextPage} onClick={() => updatePage(nextPage)}>
            Next
          </Button>
        </div>
      </div>

      <CycleDuePanel orgId={orgId} branches={branches} />

      <CreateStockTakeDialog
        orgId={orgId}
        open={createOpen}
        onOpenChange={setCreateOpen}
        branches={branches}
      />
      <GenerateCycleCountDialog
        orgId={orgId}
        open={generateCycleOpen}
        onOpenChange={setGenerateCycleOpen}
        branches={branches}
      />
    </div>
  )
}

function StockTakeListSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-48" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
