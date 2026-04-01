"use client"

import { useMemo, useState } from "react"

import { ConfirmDialog } from "@/components/shared/ConfirmDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useClosePeriodMutations } from "@/lib/hooks/close-periods/useClosePeriodMutations"
import { useClosePeriodSnapshots } from "@/lib/hooks/close-periods/useClosePeriodSnapshots"
import { getApiErrorMessage } from "@/lib/api"
import type { ClosePeriod, ClosePeriodStatus, CloseSnapshot } from "@/lib/types/close-periods"

interface ClosePeriodPanelProps {
  period: ClosePeriod | null
  orgId: string
  canWrite: boolean
  onClose: () => void
  onPeriodUpdated: (period: ClosePeriod) => void
}

function formatPeriodDate(dateStr: string): string {
  const [year, month, day] = dateStr.split("-").map(Number)
  return new Date(year, month - 1, day).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  })
}

function formatPeriodRange(period: ClosePeriod): string {
  return `${formatPeriodDate(period.start_date)} – ${formatPeriodDate(period.end_date)}`
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

function getStatusBadgeVariant(
  status: ClosePeriodStatus,
): "default" | "secondary" | "outline" {
  if (status === "OPEN") return "outline"
  if (status === "CLOSING") return "secondary"
  return "default"
}

function exportSnapshotCSV(rows: CloseSnapshot[], periodLabel: string) {
  const escape = (v: string) => (v.includes(",") ? `"${v}"` : v)
  const headers = ["Item", "SKU", "Branch", "Qty", "Avg Cost", "Latest Cost", "Avg Value", "Latest Value"]
  const csvRows = rows.map((snap) => [
    escape(snap.item.name),
    escape(snap.item.sku),
    escape(snap.branch.name),
    snap.quantity_on_hand,
    snap.average_unit_cost ?? "",
    snap.latest_unit_cost ?? "",
    snap.average_valuation ?? "",
    snap.latest_valuation ?? "",
  ])
  const csv = [headers, ...csvRows].map((r) => r.join(",")).join("\n")
  const blob = new Blob([csv], { type: "text/csv" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `snapshot-${periodLabel}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export function ClosePeriodPanel({
  period,
  orgId,
  canWrite,
  onClose,
  onPeriodUpdated,
}: ClosePeriodPanelProps) {
  const { closePeriod, reopenPeriod } = useClosePeriodMutations(orgId)

  const [confirmClose, setConfirmClose] = useState(false)
  const [confirmReopen, setConfirmReopen] = useState(false)
  const [actionError, setActionError] = useState("")

  const [branchFilter, setBranchFilter] = useState("")
  const [searchFilter, setSearchFilter] = useState("")

  const snapshotsQuery = useClosePeriodSnapshots({
    orgId,
    periodId: period?.status === "CLOSED" ? (period?.id ?? "") : "",
  })

  const branches = useMemo(() => {
    const all = snapshotsQuery.data ?? []
    const seen = new Map<string, string>()
    for (const snap of all) {
      seen.set(snap.branch.id, snap.branch.name)
    }
    return Array.from(seen.entries()).map(([id, name]) => ({ id, name }))
  }, [snapshotsQuery.data])

  const filteredSnapshots = useMemo(() => {
    let rows = snapshotsQuery.data ?? []
    if (branchFilter) {
      rows = rows.filter((s) => s.branch.id === branchFilter)
    }
    if (searchFilter.trim().length >= 2) {
      const q = searchFilter.trim().toLowerCase()
      rows = rows.filter(
        (s) =>
          s.item.name.toLowerCase().includes(q) ||
          s.item.sku.toLowerCase().includes(q),
      )
    }
    return rows
  }, [snapshotsQuery.data, branchFilter, searchFilter])

  async function handleClose() {
    if (!period) return
    try {
      setActionError("")
      const updated = await closePeriod.mutateAsync(period.id)
      onPeriodUpdated(updated)
    } catch (err) {
      setActionError(
        getApiErrorMessage(err, "Could not close the period. Check that all items have cost data."),
      )
    }
  }

  async function handleReopen() {
    if (!period) return
    try {
      setActionError("")
      const updated = await reopenPeriod.mutateAsync(period.id)
      onPeriodUpdated(updated)
    } catch (err) {
      setActionError(getApiErrorMessage(err, "Could not reopen the period."))
    }
  }

  function handleOpenChange(open: boolean) {
    if (!open) {
      setActionError("")
      setBranchFilter("")
      setSearchFilter("")
      onClose()
    }
  }

  const periodLabel = period
    ? `${period.start_date}-to-${period.end_date}`
    : ""

  return (
    <>
      <Sheet open={!!period} onOpenChange={handleOpenChange}>
        <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-2xl">
          {period ? (
            <div className="space-y-6">
              <SheetHeader>
                <SheetTitle>{formatPeriodRange(period)}</SheetTitle>
                <SheetDescription>
                  <Badge variant={getStatusBadgeVariant(period.status)}>
                    {period.status}
                  </Badge>
                </SheetDescription>
              </SheetHeader>

              {/* Details */}
              <div className="space-y-3 rounded-xl border border-border p-4 text-sm">
                <DetailRow label="Notes" value={period.notes || "—"} />
                <DetailRow label="Closed by" value={period.closed_by?.username ?? "—"} />
                <DetailRow label="Closed at" value={formatDateTime(period.closed_at)} />
                {period.reopened_by || period.reopened_at ? (
                  <>
                    <DetailRow label="Reopened by" value={period.reopened_by?.username ?? "—"} />
                    <DetailRow label="Reopened at" value={formatDateTime(period.reopened_at)} />
                  </>
                ) : null}
              </div>

              {/* Actions */}
              {canWrite ? (
                <div className="space-y-2">
                  {period.status === "OPEN" ? (
                    <Button
                      variant="outline"
                      className="border-red-300 text-red-700 hover:bg-red-50"
                      onClick={() => setConfirmClose(true)}
                      disabled={closePeriod.isPending}
                    >
                      Close Period
                    </Button>
                  ) : period.status === "CLOSED" ? (
                    <Button
                      variant="outline"
                      onClick={() => setConfirmReopen(true)}
                      disabled={reopenPeriod.isPending}
                    >
                      Reopen Period
                    </Button>
                  ) : (
                    <Button variant="outline" disabled>
                      Closing…
                    </Button>
                  )}

                  {actionError ? (
                    <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                      {actionError}
                    </div>
                  ) : null}
                </div>
              ) : null}

              {/* Snapshots — only when CLOSED */}
              {period.status === "CLOSED" ? (
                <div className="space-y-4">
                  <h3 className="font-semibold">Snapshot</h3>

                  <div className="flex flex-col gap-3 sm:flex-row">
                    <select
                      value={branchFilter}
                      onChange={(e) => setBranchFilter(e.target.value)}
                      className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-sm outline-none"
                    >
                      <option value="">All branches</option>
                      {branches.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.name}
                        </option>
                      ))}
                    </select>

                    <Input
                      placeholder="Search by item or SKU"
                      value={searchFilter}
                      onChange={(e) => setSearchFilter(e.target.value)}
                      className="h-9 sm:max-w-xs"
                    />
                  </div>

                  {snapshotsQuery.isLoading ? (
                    <div className="space-y-2">
                      {[...Array(4)].map((_, i) => (
                        <Skeleton key={i} className="h-10 w-full" />
                      ))}
                    </div>
                  ) : filteredSnapshots.length === 0 ? (
                    <p className="py-6 text-center text-sm text-muted-foreground">
                      No snapshot rows found.
                    </p>
                  ) : (
                    <div className="overflow-x-auto rounded-md border border-border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Item</TableHead>
                            <TableHead>SKU</TableHead>
                            <TableHead>Branch</TableHead>
                            <TableHead className="text-right">Qty</TableHead>
                            <TableHead className="text-right">Avg Cost</TableHead>
                            <TableHead className="text-right">Latest Cost</TableHead>
                            <TableHead className="text-right">Avg Value</TableHead>
                            <TableHead className="text-right">Latest Value</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {filteredSnapshots.map((snap) => (
                            <TableRow key={snap.id}>
                              <TableCell>{snap.item.name}</TableCell>
                              <TableCell className="font-mono text-xs">{snap.item.sku}</TableCell>
                              <TableCell>{snap.branch.name}</TableCell>
                              <TableCell className="text-right">
                                {parseFloat(snap.quantity_on_hand).toLocaleString()}
                              </TableCell>
                              <TableCell className="text-right">
                                {snap.average_unit_cost ?? "—"}
                              </TableCell>
                              <TableCell className="text-right">
                                {snap.latest_unit_cost ?? "—"}
                              </TableCell>
                              <TableCell className="text-right">
                                {snap.average_valuation ?? "—"}
                              </TableCell>
                              <TableCell className="text-right">
                                {snap.latest_valuation ?? "—"}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}

                  {filteredSnapshots.length > 0 ? (
                    <Button
                      variant="outline"
                      onClick={() => exportSnapshotCSV(filteredSnapshots, periodLabel)}
                    >
                      Export CSV
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </SheetContent>
      </Sheet>

      <ConfirmDialog
        open={confirmClose}
        onOpenChange={setConfirmClose}
        title="Close this period?"
        description="Are you sure you want to close this period? No movements will be allowed for dates within this period after closing."
        confirmLabel="Close Period"
        onConfirm={() => {
          setConfirmClose(false)
          void handleClose()
        }}
        destructive
      />

      <ConfirmDialog
        open={confirmReopen}
        onOpenChange={setConfirmReopen}
        title="Reopen this period?"
        description="Reopening will allow movements within this period again. Existing snapshots are kept but will no longer be authoritative."
        confirmLabel="Reopen Period"
        onConfirm={() => {
          setConfirmReopen(false)
          void handleReopen()
        }}
      />
    </>
  )
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="w-28 shrink-0 text-muted-foreground">{label}:</span>
      <span>{value}</span>
    </div>
  )
}
