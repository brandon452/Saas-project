"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { GRBranch } from "@/lib/hooks/goods-receipts/useGRBranches"
import type { Supplier } from "@/lib/types/suppliers"

interface GoodsReceiptFiltersProps {
  branches: GRBranch[]
  suppliers: Supplier[]
}

export function GoodsReceiptFilters({ branches, suppliers }: GoodsReceiptFiltersProps) {
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  const receiptType = searchParams.get("receipt_type") ?? ""
  const branch = searchParams.get("branch") ?? ""
  const supplier = searchParams.get("supplier") ?? ""
  const dateAfter = searchParams.get("date_after") ?? ""
  const dateBefore = searchParams.get("date_before") ?? ""

  const hasInvalidDateRange = !!dateAfter && !!dateBefore && dateAfter > dateBefore

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

  return (
    <div className="grid gap-4 rounded-xl border border-border bg-card p-4 md:grid-cols-2 xl:grid-cols-6">
      <div className="space-y-2">
        <Label htmlFor="receipt_type">Receipt type</Label>
        <select
          id="receipt_type"
          value={receiptType}
          onChange={(event) => updateFilter("receipt_type", event.target.value)}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
        >
          <option value="">All types</option>
          <option value="PO_RECEIPT">PO Receipt</option>
          <option value="DIRECT_RECEIPT">Direct Receipt</option>
        </select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="branch">Branch</Label>
        <select
          id="branch"
          value={branch}
          onChange={(event) => updateFilter("branch", event.target.value)}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
        >
          <option value="">All branches</option>
          {branches.map((option) => (
            <option key={option.id} value={option.id}>
              {option.name}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="supplier">Supplier</Label>
        <select
          id="supplier"
          value={supplier}
          onChange={(event) => updateFilter("supplier", event.target.value)}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
        >
          <option value="">All suppliers</option>
          {suppliers.map((option) => (
            <option key={option.id} value={String(option.id)}>
              {option.display_name}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="date_after">Date from</Label>
        <Input
          id="date_after"
          type="date"
          value={dateAfter}
          onChange={(event) => updateFilter("date_after", event.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="date_before">Date to</Label>
        <Input
          id="date_before"
          type="date"
          value={dateBefore}
          onChange={(event) => updateFilter("date_before", event.target.value)}
        />
      </div>

      <div className="flex items-end">
        <Button variant="outline" className="w-full justify-center" onClick={clearFilters}>
          Clear filters
        </Button>
      </div>

      {hasInvalidDateRange ? (
        <div className="md:col-span-2 xl:col-span-6">
          <p className="text-sm text-red-600">Date from must be on or before date to.</p>
        </div>
      ) : null}
    </div>
  )
}
