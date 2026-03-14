"use client"

import { useCallback, useEffect, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { CreateSupplierDialog } from "@/components/suppliers/CreateSupplierDialog"
import { SupplierPanel } from "@/components/suppliers/SupplierPanel"
import { SupplierStatusBadge } from "@/components/suppliers/SupplierStatusBadge"
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
import { useSuppliers } from "@/lib/hooks/suppliers/useSuppliers"
import { useOrg } from "@/lib/hooks/useOrg"
import type { Supplier } from "@/lib/types/suppliers"

export default function SuppliersPage() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { orgId, canAccess } = useOrg()

  const [selectedSupplier, setSelectedSupplier] = useState<Supplier | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [searchDraft, setSearchDraft] = useState(searchParams.get("search") ?? "")

  const page = Number.parseInt(searchParams.get("page") ?? "1", 10) || 1
  const search = searchParams.get("search") ?? ""
  const isActiveParam = searchParams.get("is_active")
  const isActive =
    isActiveParam === "true" ? true : isActiveParam === "false" ? false : null

  const suppliersQuery = useSuppliers({
    orgId,
    page,
    search: search || undefined,
    isActive,
  })

  useEffect(() => {
    setSearchDraft(search)
  }, [search])

  const updateParams = useCallback((next: Record<string, string | null>) => {
    const params = new URLSearchParams(searchParams.toString())

    for (const [key, value] of Object.entries(next)) {
      if (value === null || value === "") {
        params.delete(key)
      } else {
        params.set(key, value)
      }
    }

    const query = params.toString()
    router.replace(query ? `${pathname}?${query}` : pathname)
  }, [pathname, router, searchParams])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (searchDraft === search) return
      updateParams({ search: searchDraft || null, page: "1" })
    }, 300)

    return () => window.clearTimeout(timer)
  }, [searchDraft, search, updateParams])

  const canManage = canAccess(["OWNER", "ADMIN"])
  const errorMessage = suppliersQuery.error instanceof Error ? suppliersQuery.error.message : ""

  if (suppliersQuery.isLoading) {
    return <SupplierListSkeleton />
  }

  if (errorMessage.includes("403")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view suppliers in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (suppliersQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load suppliers</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            There was a problem loading suppliers. Try again.
          </p>
          <Button onClick={() => void suppliersQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const suppliers = suppliersQuery.data?.results ?? []
  const count = suppliersQuery.data?.count ?? 0
  const actionLabel = canManage ? "View / Edit" : "View"

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Suppliers</h1>
          <p className="text-sm text-muted-foreground">
            Manage suppliers available for procurement workflows.
          </p>
        </div>
        {canManage ? <Button onClick={() => setCreateOpen(true)}>New Supplier</Button> : null}
      </div>

      <div className="grid gap-4 rounded-xl border border-border bg-card p-4 md:grid-cols-[2fr_1fr]">
        <div className="space-y-2">
          <Label htmlFor="supplier-search">Name search</Label>
          <Input
            id="supplier-search"
            value={searchDraft}
            placeholder="Search supplier name"
            onChange={(event) => setSearchDraft(event.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="supplier-status">Status</Label>
          <select
            id="supplier-status"
            value={isActiveParam ?? ""}
            onChange={(event) =>
              updateParams({
                is_active: event.target.value || null,
                page: "1",
              })
            }
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            <option value="">All</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          {suppliers.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No suppliers found for the current filters.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created At</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {suppliers.map((supplier) => (
                  <TableRow
                    key={supplier.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => {
                      setSelectedSupplier(supplier)
                      setPanelOpen(true)
                    }}
                  >
                    <TableCell className="font-medium">{supplier.name}</TableCell>
                    <TableCell>
                      <SupplierStatusBadge isActive={supplier.is_active} />
                    </TableCell>
                    <TableCell>{new Date(supplier.created_at).toLocaleDateString()}</TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        onClick={(event) => {
                          event.stopPropagation()
                          setSelectedSupplier(supplier)
                          setPanelOpen(true)
                        }}
                      >
                        {actionLabel}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">Total suppliers: {count}</p>
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            disabled={page <= 1}
            onClick={() => updateParams({ page: String(page - 1) })}
          >
            Previous
          </Button>
          <span className="text-sm font-medium">Page {page}</span>
          <Button
            variant="ghost"
            disabled={!suppliersQuery.data?.next}
            onClick={() => updateParams({ page: String(page + 1) })}
          >
            Next
          </Button>
        </div>
      </div>

      {canManage ? (
        <CreateSupplierDialog orgId={orgId} open={createOpen} onOpenChange={setCreateOpen} />
      ) : null}

      <SupplierPanel
        orgId={orgId}
        supplier={selectedSupplier}
        open={panelOpen}
        onOpenChange={setPanelOpen}
        onSupplierChange={(supplier) => setSelectedSupplier(supplier)}
      />
    </div>
  )
}

function SupplierListSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-40" />
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
