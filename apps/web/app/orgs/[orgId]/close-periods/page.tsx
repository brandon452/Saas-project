"use client"

import { useMemo, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { ClosePeriodPanel } from "@/components/close-periods/ClosePeriodPanel"
import { CreateClosePeriodDialog } from "@/components/close-periods/CreateClosePeriodDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
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
import { useAuth } from "@/lib/hooks/useAuth"
import { useOrg } from "@/lib/hooks/useOrg"
import type { ClosePeriod, ClosePeriodStatus } from "@/lib/types/close-periods"

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

export default function ClosePeriodsPage() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { user, isLoading: authLoading } = useAuth()
  const { orgId, role, isParentUser, canAccess } = useOrg()

  const [selectedPeriod, setSelectedPeriod] = useState<ClosePeriod | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  const isParentAdmin = user?.parent_role === "PARENT_ADMIN"
  const canView = (!isParentUser && canAccess(["OWNER", "ADMIN"])) || isParentAdmin
  const canWrite = (!isParentUser && role === "OWNER") || isParentAdmin

  const statusFilter = searchParams.get("status") ?? ""

  const periodsQuery = useClosePeriods({ orgId: canView ? orgId : "" })

  const periods = useMemo(() => {
    const all = periodsQuery.data ?? []
    if (!statusFilter) return all
    return all.filter((p) => p.status === statusFilter)
  }, [periodsQuery.data, statusFilter])

  function updateStatus(value: string) {
    const params = new URLSearchParams(searchParams.toString())
    if (value) {
      params.set("status", value)
    } else {
      params.delete("status")
    }
    const qs = params.toString()
    router.replace(qs ? `${pathname}?${qs}` : pathname)
  }

  if (authLoading || periodsQuery.isLoading) {
    return <ClosePeriodsPageSkeleton />
  }

  if (!canView) {
    return (
      <Card>
        <div className="p-6">
          <h2 className="text-lg font-semibold">Permission denied</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            You do not have permission to view close periods in this organisation.
          </p>
        </div>
      </Card>
    )
  }

  if (periodsQuery.isError) {
    const msg = periodsQuery.error instanceof Error ? periodsQuery.error.message : ""
    if (msg.includes("403")) {
      return (
        <Card>
          <div className="p-6">
            <h2 className="text-lg font-semibold">Permission denied</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              You do not have permission to view close periods in this organisation.
            </p>
          </div>
        </Card>
      )
    }
    return (
      <Card>
        <div className="p-6 space-y-4">
          <h2 className="text-lg font-semibold">Could not load close periods</h2>
          <p className="text-sm text-muted-foreground">
            There was a problem loading close periods. Try again.
          </p>
          <Button onClick={() => void periodsQuery.refetch()}>Retry</Button>
        </div>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Close Periods</h1>
          <p className="text-sm text-muted-foreground">
            Manage inventory period closes and view historical snapshots.
          </p>
        </div>
        {canWrite ? (
          <Button onClick={() => setShowCreate(true)}>Create Period</Button>
        ) : null}
      </div>

      {/* Filter bar */}
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-3">
          <label htmlFor="cp-status-filter" className="text-sm font-medium">
            Status
          </label>
          <select
            id="cp-status-filter"
            value={statusFilter}
            onChange={(e) => updateStatus(e.target.value)}
            className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-sm outline-none"
          >
            <option value="">All</option>
            <option value="OPEN">Open</option>
            <option value="CLOSED">Closed</option>
          </select>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          {periods.length === 0 ? (
            <p className="p-8 text-center text-sm text-muted-foreground">
              {(periodsQuery.data ?? []).length === 0
                ? "No close periods yet."
                : "No periods match the current filter."}
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Period</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Closed by</TableHead>
                  <TableHead>Closed at</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {periods.map((period) => (
                  <TableRow
                    key={period.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setSelectedPeriod(period)}
                  >
                    <TableCell className="font-medium">
                      {formatPeriodRange(period)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={getStatusBadgeVariant(period.status)}>
                        {period.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{period.closed_by?.username ?? "—"}</TableCell>
                    <TableCell>{formatDateTime(period.closed_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ClosePeriodPanel
        period={selectedPeriod}
        orgId={orgId}
        canWrite={canWrite}
        onClose={() => setSelectedPeriod(null)}
        onPeriodUpdated={(updated) => setSelectedPeriod(updated)}
      />

      <CreateClosePeriodDialog
        orgId={orgId}
        open={showCreate}
        onOpenChange={setShowCreate}
        onCreated={(period) => {
          setShowCreate(false)
          setSelectedPeriod(period)
        }}
      />
    </div>
  )
}

function ClosePeriodsPageSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-48" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}
