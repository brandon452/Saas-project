"use client"

import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { BranchTransferDirectionBadge } from "@/components/branch-transfers/BranchTransferDirectionBadge"
import { BranchTransferStatusBadge } from "@/components/branch-transfers/BranchTransferStatusBadge"
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
import { useBranchTransfers } from "@/lib/hooks/branch-transfers/useBranchTransfers"
import { useNetworkBranches } from "@/lib/hooks/branch-transfers/useNetworkBranches"
import { useExportCsv } from "@/lib/hooks/useExportCsv"
import { useOrg } from "@/lib/hooks/useOrg"

const STATUS_OPTIONS = [
  "DRAFT",
  "APPROVED",
  "IN_TRANSIT",
  "RECEIVED_COMPLETE",
  "RECEIVED_WITH_VARIANCE",
  "CANCELLED",
] as const

export default function BranchTransfersPage() {
  const { orgId, role } = useOrg()
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  const status = searchParams.get("status") ?? ""
  const page = searchParams.get("page") ?? "1"

  const transfersQuery = useBranchTransfers({
    orgId,
    status: status || undefined,
    page,
  })
  const networkBranchesQuery = useNetworkBranches(orgId)

  const { exportStatus, exportError, triggerExport } = useExportCsv()

  function handleExport() {
    const params = new URLSearchParams()
    if (status) params.set("status", status)
    void triggerExport(`orgs/${orgId}/branch-transfers/export/csv/`, params)
  }

  const branchMap = new Map((networkBranchesQuery.data ?? []).map((branch) => [branch.id, branch]))
  const errorMessage = transfersQuery.error instanceof Error ? transfersQuery.error.message : ""
  const currentPage = Number.parseInt(page, 10) || 1

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

  function clearFilters() {
    const params = new URLSearchParams()
    params.set("page", "1")
    router.replace(`${pathname}?${params.toString()}`)
  }

  if (transfersQuery.isLoading) {
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
            You do not have permission to view branch transfers in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (transfersQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load branch transfers</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            There was a problem loading branch transfers. Try again.
          </p>
          <Button onClick={() => void transfersQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const transfers = transfersQuery.data?.results ?? []
  const count = transfersQuery.data?.count ?? 0

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Branch Transfers</h1>
          <p className="text-sm text-muted-foreground">
            Track stock transfers across branches and organisations.
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
          {role === "OWNER" || role === "ADMIN" ? (
            <Link
              href={`/orgs/${orgId}/branch-transfers/new`}
              className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
            >
              New Branch Transfer
            </Link>
          ) : null}
        </div>
      </div>
      {exportStatus === "error" && exportError
        ? <p className="text-sm text-destructive">{exportError}</p>
        : null}

      <div className="grid gap-4 rounded-xl border border-border bg-card p-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,14rem),1fr))]">
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
        <div className="flex items-end">
          <Button variant="outline" className="w-full justify-center" onClick={clearFilters}>
            Clear filters
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          {transfers.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No branch transfers found for the current filters.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Direction</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>From Branch</TableHead>
                  <TableHead>To Branch</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Dispatched</TableHead>
                  <TableHead>Received</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transfers.map((transfer) => (
                  <TableRow
                    key={transfer.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => router.push(`/orgs/${orgId}/branch-transfers/${transfer.id}`)}
                  >
                    <TableCell>
                      <BranchTransferDirectionBadge transfer={transfer} orgId={orgId} />
                    </TableCell>
                    <TableCell>
                      <BranchTransferStatusBadge status={transfer.status} />
                    </TableCell>
                    <TableCell>{branchMap.get(transfer.from_branch)?.name ?? "\u2014"}</TableCell>
                    <TableCell>{branchMap.get(transfer.to_branch)?.name ?? "\u2014"}</TableCell>
                    <TableCell>{new Date(transfer.created_at).toLocaleDateString()}</TableCell>
                    <TableCell>
                      {transfer.dispatched_at
                        ? new Date(transfer.dispatched_at).toLocaleDateString()
                        : "\u2014"}
                    </TableCell>
                    <TableCell>
                      {transfer.received_at
                        ? new Date(transfer.received_at).toLocaleDateString()
                        : "\u2014"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">Total branch transfers: {count}</p>
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
            disabled={!transfersQuery.data?.next}
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
