"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { ConfirmDialog } from "@/components/shared/ConfirmDialog"
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
import { useBranchItemCatalog } from "@/lib/hooks/branch-items/useBranchItemCatalog"
import { useBranchItemMutations } from "@/lib/hooks/branch-items/useBranchItemMutations"
import { usePOBranches } from "@/lib/hooks/purchase-orders/usePOBranches"
import { useOrg } from "@/lib/hooks/useOrg"
import type { BranchCatalogRow } from "@/lib/types/branch-items"

function getMutationErrorMessage(error: unknown, action: "enable" | "disable") {
  const message = error instanceof Error ? error.message : ""

  if (message.includes("403")) {
    return action === "enable"
      ? "You do not have permission to enable items at this branch."
      : "You do not have permission to disable items at this branch."
  }

  if (message.includes("400")) {
    return action === "enable"
      ? "Could not enable this item at the selected branch."
      : "Could not disable this item at the selected branch."
  }

  return action === "enable" ? "Could not enable item." : "Could not disable item."
}

export default function BranchItemsPage() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { orgId, canAccess } = useOrg()

  const canEdit = canAccess(["OWNER", "ADMIN"])
  const branchId = searchParams.get("branch") ?? ""
  const search = searchParams.get("search") ?? ""
  const page = searchParams.get("page") ?? "1"

  const [searchDraft, setSearchDraft] = useState(search)
  const [pendingRowId, setPendingRowId] = useState<string | null>(null)
  const [error, setError] = useState("")
  const [confirmRow, setConfirmRow] = useState<BranchCatalogRow | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulkError, setBulkError] = useState("")
  const [selectedDeactivateIds, setSelectedDeactivateIds] = useState<Set<number>>(new Set())
  const [bulkDeactivateError, setBulkDeactivateError] = useState("")
  const [confirmBulkDeactivate, setConfirmBulkDeactivate] = useState(false)

  const branchesQuery = usePOBranches(orgId)
  const catalogQuery = useBranchItemCatalog({
    orgId,
    branchId,
    search: search || undefined,
    page,
  })
  const { enableBranchItem, disableBranchItem, bulkActivateBranchItems, bulkDeactivateBranchItems } = useBranchItemMutations(orgId, branchId)

  useEffect(() => {
    setSearchDraft(search)
  }, [search])

  const updateParams = useCallback(
    (next: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString())

      for (const [key, value] of Object.entries(next)) {
        if (!value) {
          params.delete(key)
        } else {
          params.set(key, value)
        }
      }

      const query = params.toString()
      router.replace(query ? `${pathname}?${query}` : pathname)
    },
    [pathname, router, searchParams],
  )

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const trimmed = searchDraft.trim()

      if (!branchId) return

      if (trimmed.length >= 2) {
        if (trimmed !== search) {
          setSelectedIds(new Set())
          setBulkError("")
          setSelectedDeactivateIds(new Set())
          setBulkDeactivateError("")
          updateParams({ search: trimmed, page: "1" })
        }
        return
      }

      if (search) {
        setSelectedIds(new Set())
        setBulkError("")
        setSelectedDeactivateIds(new Set())
        setBulkDeactivateError("")
        updateParams({ search: null, page: "1" })
      }
    }, 300)

    return () => window.clearTimeout(timer)
  }, [branchId, searchDraft, search, updateParams])

  const items = useMemo(() => catalogQuery.data?.results ?? [], [catalogQuery.data?.results])
  const count = catalogQuery.data?.count ?? 0
  const disabledItems = items.filter((r) => !r.is_enabled)
  const allDisabledSelected =
    disabledItems.length > 0 && disabledItems.every((r) => selectedIds.has(r.id))
  const columns = useMemo(
    () => (canEdit ? ["Name", "SKU", "Status", "Actions"] : ["Name", "SKU", "Status"]),
    [canEdit],
  )
  const branches = branchesQuery.data ?? []
  const catalogErrorMessage = catalogQuery.error instanceof Error ? catalogQuery.error.message : ""
  const branchErrorMessage = branchesQuery.error instanceof Error ? branchesQuery.error.message : ""
  const showBranchPermissionError = branchErrorMessage.includes("403")
  const showCatalogPermissionError = branchId && catalogErrorMessage.includes("403")
  const showCatalogError = branchId && catalogQuery.isError && !showCatalogPermissionError
  const showBranchError = branchesQuery.isError && !showBranchPermissionError

  async function handleEnable(row: BranchCatalogRow) {
    try {
      setPendingRowId(row.id)
      setError("")
      await enableBranchItem.mutateAsync({
        org_item: row.id,
        branch: branchId,
      })
    } catch (err) {
      setError(getMutationErrorMessage(err, "enable"))
    } finally {
      setPendingRowId(null)
    }
  }

  async function handleDisable() {
    if (!confirmRow?.branch_item_id) return

    try {
      setPendingRowId(confirmRow.id)
      setError("")
      await disableBranchItem.mutateAsync(confirmRow.branch_item_id)
      setConfirmRow(null)
    } catch (err) {
      setError(getMutationErrorMessage(err, "disable"))
    } finally {
      setPendingRowId(null)
    }
  }

  async function handleBulkActivate() {
    if (!branchId || selectedIds.size === 0) return
    try {
      setBulkError("")
      await bulkActivateBranchItems.mutateAsync({
        branch: branchId,
        org_items: Array.from(selectedIds),
      })
      setSelectedIds(new Set())
    } catch {
      setBulkError("Could not activate selected items. Please try again.")
    }
  }

  async function handleBulkDeactivate() {
    if (!branchId || selectedDeactivateIds.size === 0) return
    try {
      setBulkDeactivateError("")
      await bulkDeactivateBranchItems.mutateAsync({
        branch: branchId,
        branch_items: Array.from(selectedDeactivateIds),
      })
      setSelectedDeactivateIds(new Set())
      setConfirmBulkDeactivate(false)
    } catch {
      setBulkDeactivateError("Could not deactivate selected items. Please try again.")
    }
  }

  let emptyMessage = "No active org items available for branch assignment"
  if (!branchId) {
    emptyMessage = "Select a branch to view its item catalog"
  } else if (search) {
    emptyMessage = "No items match your search"
  }

  return (
    <>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Branch Items</h1>
          <p className="text-sm text-muted-foreground">
            View and manage which org items are enabled for each branch.
          </p>
        </div>

        <div className="grid gap-4 rounded-xl border border-border bg-card p-4 md:grid-cols-[1fr_2fr]">
          <div className="space-y-2">
            <Label htmlFor="branch-items-branch">Branch</Label>
            <select
              id="branch-items-branch"
              value={branchId}
              disabled={branchesQuery.isLoading || showBranchError || showBranchPermissionError}
              onChange={(event) => {
                setError("")
                setSelectedIds(new Set())
                setBulkError("")
                setSelectedDeactivateIds(new Set())
                setBulkDeactivateError("")
                updateParams({
                  branch: event.target.value || null,
                  search: null,
                  page: "1",
                })
              }}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none disabled:cursor-not-allowed disabled:opacity-50"
            >
              <option value="">Select a branch</option>
              {branches.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="branch-items-search">Search</Label>
            <Input
              id="branch-items-search"
              value={searchDraft}
              placeholder="Search by item name or SKU"
              disabled={!branchId}
              onChange={(event) => setSearchDraft(event.target.value)}
            />
          </div>
        </div>

        {canEdit && branchId ? (
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              {bulkError ? (
                <p className="text-sm text-red-600">{bulkError}</p>
              ) : null}
              {bulkDeactivateError ? (
                <p className="text-sm text-red-600">{bulkDeactivateError}</p>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              {selectedIds.size > 0 ? (
                <Button
                  disabled={bulkActivateBranchItems.isPending}
                  onClick={() => void handleBulkActivate()}
                >
                  {bulkActivateBranchItems.isPending
                    ? "Activating..."
                    : `Activate ${selectedIds.size} Item${selectedIds.size === 1 ? "" : "s"}`}
                </Button>
              ) : null}
              {selectedDeactivateIds.size > 0 ? (
                <Button
                  variant="destructive"
                  disabled={bulkDeactivateBranchItems.isPending}
                  onClick={() => setConfirmBulkDeactivate(true)}
                >
                  {`Deactivate ${selectedDeactivateIds.size} Item${selectedDeactivateIds.size === 1 ? "" : "s"}`}
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}

        {error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {showBranchPermissionError ? (
          <Card>
            <CardHeader>
              <CardTitle>Permission denied</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                You do not have permission to view branch item catalogs in this organisation.
              </p>
            </CardContent>
          </Card>
        ) : showBranchError ? (
          <Card>
            <CardHeader>
              <CardTitle>Could not load branches</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                There was a problem loading branches. Try again.
              </p>
              <Button onClick={() => void branchesQuery.refetch()}>Retry</Button>
            </CardContent>
          </Card>
        ) : !branchId ? (
          <Card>
            <CardContent className="p-8 text-center text-sm text-muted-foreground">
              {emptyMessage}
            </CardContent>
          </Card>
        ) : catalogQuery.isLoading ? (
            <Card>
              <CardContent className="p-0">
                <BranchItemsTableSkeleton columns={columns} showSelect={canEdit && !!branchId} />
              </CardContent>
            </Card>
        ) : showCatalogPermissionError ? (
          <Card>
            <CardHeader>
              <CardTitle>Permission denied</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                You do not have permission to view this branch&apos;s item catalog.
              </p>
            </CardContent>
          </Card>
        ) : showCatalogError ? (
          <Card>
            <CardHeader>
              <CardTitle>Could not load branch items</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                There was a problem loading branch items. Try again.
              </p>
              <Button onClick={() => void catalogQuery.refetch()}>Retry</Button>
            </CardContent>
          </Card>
        ) : (
          <>
            <Card>
              <CardContent className="p-0">
                {items.length === 0 ? (
                  <div className="p-8 text-center text-sm text-muted-foreground">{emptyMessage}</div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {canEdit && branchId ? (
                          <TableHead className="w-10" />
                        ) : null}
                        {columns.map((column) => (
                          <TableHead key={column}>{column}</TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {items.map((row) => {
                        const isPending = pendingRowId === row.id

                        return (
                          <TableRow key={row.id}>
                            {canEdit && branchId ? (
                              <TableCell className="w-10">
                                {!row.is_enabled ? (
                                  <input
                                    type="checkbox"
                                    checked={selectedIds.has(row.id)}
                                    onChange={() => {
                                      setSelectedIds((prev) => {
                                        const next = new Set(prev)
                                        if (next.has(row.id)) {
                                          next.delete(row.id)
                                        } else {
                                          next.add(row.id)
                                        }
                                        return next
                                      })
                                    }}
                                  />
                                ) : row.branch_item_id !== null ? (
                                  <input
                                    type="checkbox"
                                    checked={selectedDeactivateIds.has(row.branch_item_id)}
                                    onChange={() => {
                                      const id = row.branch_item_id!
                                      setSelectedDeactivateIds((prev) => {
                                        const next = new Set(prev)
                                        if (next.has(id)) {
                                          next.delete(id)
                                        } else {
                                          next.add(id)
                                        }
                                        return next
                                      })
                                    }}
                                  />
                                ) : null}
                              </TableCell>
                            ) : null}
                            <TableCell className="font-medium">{row.name}</TableCell>
                            <TableCell className="font-mono">{row.sku}</TableCell>
                            <TableCell>
                              <Badge variant={row.is_enabled ? "default" : "secondary"}>
                                {row.is_enabled ? "Enabled" : "Not enabled"}
                              </Badge>
                            </TableCell>
                            {canEdit ? (
                              <TableCell>
                                {row.is_enabled ? (
                                  <Button
                                    variant="destructive"
                                    disabled={isPending}
                                    onClick={() => setConfirmRow(row)}
                                  >
                                    {isPending ? "Disabling..." : "Disable"}
                                  </Button>
                                ) : (
                                  <Button
                                    disabled={isPending}
                                    onClick={() => void handleEnable(row)}
                                  >
                                    {isPending ? "Enabling..." : "Enable"}
                                  </Button>
                                )}
                              </TableCell>
                            ) : null}
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">Total items: {count}</p>
              <div className="flex items-center gap-3">
                <Button
                  variant="ghost"
                  disabled={page === "1"}
                  onClick={() => {
                    setSelectedIds(new Set())
                    setBulkError("")
                    setSelectedDeactivateIds(new Set())
                    setBulkDeactivateError("")
                    updateParams({ page: String(Math.max(1, Number.parseInt(page, 10) - 1)) })
                  }}
                >
                  Previous
                </Button>
                <span className="text-sm font-medium">Page {page}</span>
                <Button
                  variant="ghost"
                  disabled={!catalogQuery.data?.next}
                  onClick={() => {
                    setSelectedIds(new Set())
                    setBulkError("")
                    setSelectedDeactivateIds(new Set())
                    setBulkDeactivateError("")
                    updateParams({ page: String(Number.parseInt(page, 10) + 1) })
                  }}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </div>

      <ConfirmDialog
        open={!!confirmRow}
        onOpenChange={(open) => !open && setConfirmRow(null)}
        title="Disable Branch Item"
        description="Disable this item at this branch? It will be hidden from item search and transactions."
        confirmLabel="Disable"
        onConfirm={() => {
          void handleDisable()
        }}
        destructive
      />

      <ConfirmDialog
        open={confirmBulkDeactivate}
        onOpenChange={(open) => !open && setConfirmBulkDeactivate(false)}
        title="Deactivate Branch Items"
        description={`Deactivate ${selectedDeactivateIds.size} item${selectedDeactivateIds.size === 1 ? "" : "s"} at this branch? They will be hidden from item search and transactions.`}
        confirmLabel={bulkDeactivateBranchItems.isPending ? "Deactivating..." : "Deactivate"}
        onConfirm={() => {
          void handleBulkDeactivate()
        }}
        destructive
      />
    </>
  )
}

function BranchItemsTableSkeleton({ columns, showSelect }: { columns: string[]; showSelect?: boolean }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {showSelect ? <TableHead className="w-10" /> : null}
          {columns.map((column) => (
            <TableHead key={column}>{column}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {Array.from({ length: 6 }).map((_, index) => (
          <TableRow key={index}>
            {showSelect ? (
              <TableCell className="w-10">
                <Skeleton className="h-4 w-4" />
              </TableCell>
            ) : null}
            {columns.map((column) => (
              <TableCell key={column}>
                <Skeleton className="h-5 w-full max-w-[160px]" />
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
