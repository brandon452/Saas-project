"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { CreateMasterItemDialog } from "@/components/master-items/CreateMasterItemDialog"
import { MasterItemPanel } from "@/components/master-items/MasterItemPanel"
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
import { useMasterItems } from "@/lib/hooks/master-items/useMasterItems"
import { useAuth } from "@/lib/hooks/useAuth"
import type { MasterItem } from "@/lib/types/master-items"

function getListErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : ""
  return message
}

export default function ParentMasterItemsPage() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { user } = useAuth()

  const [selectedItemId, setSelectedItemId] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [searchDraft, setSearchDraft] = useState(searchParams.get("search") ?? "")

  const isParentAdmin = user?.parent_role === "PARENT_ADMIN"
  const page = searchParams.get("page") ?? "1"
  const isActive = searchParams.get("is_active") === "false" ? "false" : "true"
  const search = searchParams.get("search") ?? ""

  const masterItemsQuery = useMasterItems({
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

  const listErrorMessage = getListErrorMessage(masterItemsQuery.error)

  const columns = useMemo(
    () =>
      isParentAdmin
        ? ["Name", "SKU", "Status", "Created", "Actions"]
        : ["Name", "SKU", "Status", "Created"],
    [isParentAdmin],
  )

  if (masterItemsQuery.isLoading) {
    return <MasterItemsListSkeleton />
  }

  if (listErrorMessage.includes("403")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view the global catalog.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (masterItemsQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load catalog items</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            There was a problem loading the global catalog. Try again.
          </p>
          <Button onClick={() => void masterItemsQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const items = masterItemsQuery.data?.results ?? []
  const count = masterItemsQuery.data?.count ?? 0

  let emptyMessage = isActive === "true" ? "No active catalog items found" : "No inactive catalog items found"
  if (search) {
    emptyMessage = "No items match your search"
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Global Catalog</h1>
          <p className="text-sm text-muted-foreground">
            Manage org-agnostic item definitions that each organization can activate and configure locally.
          </p>
        </div>
        {isParentAdmin ? <Button onClick={() => setCreateOpen(true)}>New Catalog Item</Button> : null}
      </div>

      <div className="grid gap-4 rounded-xl border border-border bg-card p-4 md:grid-cols-[2fr_1fr]">
        <div className="space-y-2">
          <Label htmlFor="master-item-search">Search catalog</Label>
          <Input
            id="master-item-search"
            value={searchDraft}
            placeholder="Search by item name or SKU"
            onChange={(event) => setSearchDraft(event.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="master-item-inactive">Status</Label>
          <label className="flex h-10 items-center gap-3 rounded-md border border-input bg-background px-3 text-sm">
            <input
              id="master-item-inactive"
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
                  <MasterItemRow
                    key={item.id}
                    item={item}
                    isParentAdmin={isParentAdmin}
                    onOpen={() => setSelectedItemId(item.id)}
                  />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">Total catalog items: {count}</p>
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
            disabled={!masterItemsQuery.data?.next}
            onClick={() => updateParams({ page: String(Number.parseInt(page, 10) + 1) })}
          >
            Next
          </Button>
        </div>
      </div>

      {isParentAdmin ? <CreateMasterItemDialog open={createOpen} onOpenChange={setCreateOpen} /> : null}

      <MasterItemPanel
        selectedId={selectedItemId}
        isParentAdmin={isParentAdmin}
        onClose={() => setSelectedItemId(null)}
        onDeactivated={() => setSelectedItemId(null)}
      />
    </div>
  )
}

function MasterItemRow({
  item,
  isParentAdmin,
  onOpen,
}: {
  item: MasterItem
  isParentAdmin: boolean
  onOpen: () => void
}) {
  return (
    <TableRow className="cursor-pointer hover:bg-muted/50" onClick={onOpen}>
      <TableCell className="font-medium">{item.name}</TableCell>
      <TableCell className="font-mono">{item.sku}</TableCell>
      <TableCell>
        <Badge variant={item.is_active ? "default" : "secondary"}>{item.is_active ? "Active" : "Inactive"}</Badge>
      </TableCell>
      <TableCell>{new Date(item.created_at).toLocaleDateString()}</TableCell>
      {isParentAdmin ? (
        <TableCell>
          <Button
            variant="ghost"
            onClick={(event) => {
              event.stopPropagation()
              onOpen()
            }}
          >
            Edit
          </Button>
        </TableCell>
      ) : null}
    </TableRow>
  )
}

function MasterItemsListSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-48" />
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
