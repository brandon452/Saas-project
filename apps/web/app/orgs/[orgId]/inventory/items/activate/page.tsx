"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
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
import { useAvailableMasterItemsPage } from "@/lib/hooks/org-items/useAvailableMasterItemsPage"
import { useOrgItemMutations } from "@/lib/hooks/org-items/useOrgItemMutations"
import { useOrg } from "@/lib/hooks/useOrg"
import { getApiErrorMessage } from "@/lib/api"

export default function BulkActivateItemsPage() {
  const router = useRouter()
  const { orgId, canAccess } = useOrg()

  const canEdit = canAccess(["OWNER", "ADMIN"])

  useEffect(() => {
    if (!canEdit) {
      router.replace(`/orgs/${orgId}/inventory/items`)
    }
  }, [canEdit, orgId, router])

  const [searchDraft, setSearchDraft] = useState("")
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(1)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => {
      setSearch(searchDraft.trim())
      setPage(1)
    }, 300)
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current)
    }
  }, [searchDraft])

  const query = useAvailableMasterItemsPage(orgId, page, search)
  const { bulkActivateItems } = useOrgItemMutations(orgId)

  const items = useMemo(() => query.data?.results ?? [], [query.data?.results])
  const count = query.data?.count ?? 0
  const pageSize = 100
  const totalPages = Math.max(1, Math.ceil(count / pageSize))

  const toggleItem = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const togglePage = useCallback(() => {
    const pageIds = items.map((i) => i.id)
    const allSelected = pageIds.every((id) => selectedIds.has(id))
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (allSelected) {
        pageIds.forEach((id) => next.delete(id))
      } else {
        pageIds.forEach((id) => next.add(id))
      }
      return next
    })
  }, [items, selectedIds])

  const handleActivate = useCallback(async () => {
    setErrorMessage(null)
    setSuccessMessage(null)
    try {
      const result = await bulkActivateItems.mutateAsync({
        master_items: Array.from(selectedIds),
      })
      setSelectedIds(new Set())
      setSuccessMessage(
        `${result.activated} item${result.activated !== 1 ? "s" : ""} added to catalog successfully.${result.already_active > 0 ? ` ${result.already_active} were already active.` : ""}`,
      )
      setTimeout(() => {
        router.push(`/orgs/${orgId}/inventory/items`)
      }, 1500)
    } catch (err) {
      setErrorMessage(getApiErrorMessage(err, "Failed to add items. Please try again."))
    }
  }, [bulkActivateItems, selectedIds, orgId, router])

  if (!canEdit) return null

  const allPageSelected = items.length > 0 && items.every((i) => selectedIds.has(i.id))
  const somePageSelected = items.some((i) => selectedIds.has(i.id))

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Bulk Add Items</h1>
          <p className="text-sm text-muted-foreground">
            Select items from the catalog to add to this organisation.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => router.push(`/orgs/${orgId}/inventory/items`)}
          >
            Cancel
          </Button>
          <Button
            disabled={selectedIds.size === 0 || bulkActivateItems.isPending}
            onClick={handleActivate}
          >
            {bulkActivateItems.isPending
              ? "Adding…"
              : `Add ${selectedIds.size > 0 ? selectedIds.size : ""} Item${selectedIds.size !== 1 ? "s" : ""}`}
          </Button>
        </div>
      </div>

      {successMessage && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          {successMessage}
        </div>
      )}

      {errorMessage && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {errorMessage}
        </div>
      )}

      <div className="rounded-xl border border-border bg-card p-4">
        <div className="space-y-2 max-w-sm">
          <Label htmlFor="bulk-activate-search">Search items</Label>
          <Input
            id="bulk-activate-search"
            value={searchDraft}
            placeholder="Filter by name or SKU"
            onChange={(e) => setSearchDraft(e.target.value)}
          />
        </div>
      </div>

      {selectedIds.size > 0 && (
        <p className="text-sm text-muted-foreground">
          {selectedIds.size} item{selectedIds.size !== 1 ? "s" : ""} selected
        </p>
      )}

      <div className="rounded-xl border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">
                <input
                  type="checkbox"
                  checked={allPageSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = somePageSelected && !allPageSelected
                  }}
                  onChange={togglePage}
                  aria-label="Select all on this page"
                  disabled={items.length === 0}
                />
              </TableHead>
              <TableHead>Name</TableHead>
              <TableHead>SKU</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {query.isLoading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-4 w-4" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-40" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                </TableRow>
              ))
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={3} className="py-10 text-center text-sm text-muted-foreground">
                  {search ? "No items match your search." : "All catalog items are already active in this organisation."}
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <TableRow
                  key={item.id}
                  className="cursor-pointer"
                  onClick={() => toggleItem(item.id)}
                >
                  <TableCell>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(item.id)}
                      onChange={() => toggleItem(item.id)}
                      onClick={(e) => e.stopPropagation()}
                      aria-label={`Select ${item.name}`}
                    />
                  </TableCell>
                  <TableCell className="font-medium">{item.name}</TableCell>
                  <TableCell className="text-muted-foreground">{item.sku}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Page {page} of {totalPages} ({count} items total)
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
