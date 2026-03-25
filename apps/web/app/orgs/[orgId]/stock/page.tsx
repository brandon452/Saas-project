"use client"

import { useMemo } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { StockFilters } from "@/components/stock/StockFilters"
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
import { useBTFromBranches } from "@/lib/hooks/branch-transfers/useBTFromBranches"
import { useStockOnHand } from "@/lib/hooks/stock/useStockOnHand"
import { formatQuantity } from "@/lib/utils/stock"
import { toRelativePath } from "@/lib/utils/pagination"

function getPageFromNext(next: string | null): string | null {
  if (!next) return null
  const relativePath = toRelativePath(next)
  const [, query = ""] = relativePath.split("?")
  return new URLSearchParams(query).get("page")
}

export default function StockPage({ params }: { params: { orgId: string } }) {
  const orgId = params.orgId
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  const branch = searchParams.get("branch") ?? ""
  const item = searchParams.get("item") ?? ""
  const page = searchParams.get("page") ?? "1"

  const stockQuery = useStockOnHand({
    orgId,
    branch: branch || undefined,
    item: item || undefined,
    page,
  })
  const branchesQuery = useBTFromBranches(orgId)

  const branches = useMemo(
    () => (branchesQuery.data ?? []).map((branchItem) => ({ id: branchItem.id, name: branchItem.name })),
    [branchesQuery.data],
  )

  function updatePage(nextPage: string | null) {
    if (!nextPage) return

    const params = new URLSearchParams(searchParams.toString())
    params.set("page", nextPage)
    router.replace(`${pathname}?${params.toString()}`)
  }

  if (stockQuery.isLoading) {
    return <StockListSkeleton />
  }

  const errorMessage = stockQuery.error instanceof Error ? stockQuery.error.message : ""

  if (errorMessage.includes("403")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view stock levels in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (stockQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load stock levels</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            There was a problem loading stock levels. Try again.
          </p>
          <Button onClick={() => void stockQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const rows = stockQuery.data?.results ?? []
  const count = stockQuery.data?.count ?? 0
  const previousPage = page === "1" ? null : String(Math.max(1, Number.parseInt(page, 10) - 1))
  const nextPage = getPageFromNext(stockQuery.data?.next ?? null)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Stock Levels</h1>
        <p className="text-sm text-muted-foreground">
          Review movement-backed stock rows across branches and items.
        </p>
      </div>

      <StockFilters
        branches={branches}
        orgId={orgId}
        selectedBranchId={branch || undefined}
      />

      <Card>
        <CardContent className="p-0">
          {rows.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No stock records found for the current filters
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item</TableHead>
                  <TableHead>SKU</TableHead>
                  <TableHead>Branch</TableHead>
                  <TableHead>Quantity</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-medium">{row.item.name}</TableCell>
                    <TableCell>{row.item.sku}</TableCell>
                    <TableCell>{row.branch.name}</TableCell>
                    <TableCell>{formatQuantity(row.quantity)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">Total stock rows: {count}</p>
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            disabled={!previousPage}
            onClick={() => updatePage(previousPage)}
          >
            Previous
          </Button>
          <span className="text-sm font-medium">Page {page}</span>
          <Button
            variant="ghost"
            disabled={!nextPage}
            onClick={() => updatePage(nextPage)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}

function StockListSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-40" />
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
