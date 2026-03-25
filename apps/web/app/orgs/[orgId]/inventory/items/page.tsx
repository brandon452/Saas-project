"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { ActivateItemDialog } from "@/components/org-items/ActivateItemDialog"
import { OrgItemPanel } from "@/components/org-items/OrgItemPanel"
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
import { useOrgItems } from "@/lib/hooks/org-items/useOrgItems"
import { useOrg } from "@/lib/hooks/useOrg"
import type { OrgItem } from "@/lib/types/org-items"

export default function OrgItemsPage() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { orgId, canAccess } = useOrg()

  const [selectedItem, setSelectedItem] = useState<OrgItem | null>(null)
  const [activateOpen, setActivateOpen] = useState(false)
  const [searchDraft, setSearchDraft] = useState(searchParams.get("search") ?? "")

  const canEdit = canAccess(["OWNER", "ADMIN"])
  const search = searchParams.get("search") ?? ""
  const isActive = searchParams.get("is_active") === "false" ? "false" : "true"
  const page = searchParams.get("page") ?? "1"

  const orgItemsQuery = useOrgItems({
    orgId,
    search: search || undefined,
    is_active: isActive,
    page,
  })

  useEffect(() => {
    if (!searchParams.get("is_active")) {
      const params = new URLSearchParams(searchParams.toString())
      params.set("is_active", "true")
      router.replace(`${pathname}?${params.toString()}`)
    }
  }, [pathname, router, searchParams])

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

      if (trimmed.length >= 2) {
        if (trimmed !== search) {
          updateParams({ search: trimmed, page: "1" })
        }
        return
      }

      if (search) {
        updateParams({ search: null, page: "1" })
      }
    }, 300)

    return () => window.clearTimeout(timer)
  }, [searchDraft, search, updateParams])

  const items = useMemo(() => orgItemsQuery.data?.results ?? [], [orgItemsQuery.data?.results])
  const count = orgItemsQuery.data?.count ?? 0

  useEffect(() => {
    if (!selectedItem) return

    const reboundItem = items.find((item) => item.id === selectedItem.id) ?? null

    if (reboundItem) {
      if (reboundItem !== selectedItem) {
        setSelectedItem(reboundItem)
      }
      return
    }

    if (!orgItemsQuery.isFetching) {
      setSelectedItem(null)
    }
  }, [items, orgItemsQuery.isFetching, selectedItem])

  const errorMessage = orgItemsQuery.error instanceof Error ? orgItemsQuery.error.message : ""

  const columns = useMemo(
    () => (canEdit ? ["Name", "SKU", "Status", "Created", "Actions"] : ["Name", "SKU", "Status", "Created"]),
    [canEdit],
  )

  if (orgItemsQuery.isLoading) {
    return <OrgItemsListSkeleton />
  }

  if (errorMessage.includes("403")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view this organisation&apos;s item catalog.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (orgItemsQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load items</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            There was a problem loading items. Try again.
          </p>
          <Button onClick={() => void orgItemsQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  let emptyMessage = "No inactive items found"
  if (search) {
    emptyMessage = "No items match your search"
  } else if (isActive === "true") {
    emptyMessage = "No active items in this org's catalog"
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Items</h1>
          <p className="text-sm text-muted-foreground">
            Browse and maintain the items activated for this organisation.
          </p>
        </div>
        {canEdit ? <Button onClick={() => setActivateOpen(true)}>Activate Item</Button> : null}
      </div>

      <div className="grid gap-4 rounded-xl border border-border bg-card p-4 md:grid-cols-[2fr_1fr]">
        <div className="space-y-2">
          <Label htmlFor="org-item-search">Search</Label>
          <Input
            id="org-item-search"
            value={searchDraft}
            placeholder="Search by item name or SKU"
            onChange={(event) => setSearchDraft(event.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="org-item-inactive">Status</Label>
          <label className="flex h-10 items-center gap-3 rounded-md border border-input bg-background px-3 text-sm">
            <input
              id="org-item-inactive"
              type="checkbox"
              checked={isActive === "false"}
              onChange={(event) =>
                updateParams({
                  is_active: event.target.checked ? "false" : "true",
                  page: "1",
                })
              }
            />
            <span>Show inactive</span>
          </label>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          {items.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">{emptyMessage}</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  {columns.map((column) => (
                    <TableHead key={column}>{column}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow
                    key={item.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setSelectedItem(item)}
                  >
                    <TableCell className="font-medium">
                      <button
                        type="button"
                        className="text-left hover:underline"
                        onClick={(event) => {
                          event.stopPropagation()
                          setSelectedItem(item)
                        }}
                      >
                        {item.name}
                      </button>
                    </TableCell>
                    <TableCell className="font-mono">{item.sku}</TableCell>
                    <TableCell>
                      <Badge variant={item.is_active ? "default" : "secondary"}>
                        {item.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell>{new Date(item.created_at).toLocaleDateString()}</TableCell>
                    {canEdit ? (
                      <TableCell>
                        <Button
                          variant="ghost"
                          onClick={(event) => {
                            event.stopPropagation()
                            setSelectedItem(item)
                          }}
                        >
                          Edit
                        </Button>
                      </TableCell>
                    ) : null}
                  </TableRow>
                ))}
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
            onClick={() => updateParams({ page: String(Math.max(1, Number.parseInt(page, 10) - 1)) })}
          >
            Previous
          </Button>
          <span className="text-sm font-medium">Page {page}</span>
          <Button
            variant="ghost"
            disabled={!orgItemsQuery.data?.next}
            onClick={() => updateParams({ page: String(Number.parseInt(page, 10) + 1) })}
          >
            Next
          </Button>
        </div>
      </div>

      {canEdit ? (
        <ActivateItemDialog
          orgId={orgId}
          open={activateOpen}
          onOpenChange={setActivateOpen}
        />
      ) : null}

      <OrgItemPanel
        item={selectedItem}
        canEdit={canEdit}
        onClose={() => setSelectedItem(null)}
        onDeactivated={() => setSelectedItem(null)}
      />
    </div>
  )
}

function OrgItemsListSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-40" />
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
