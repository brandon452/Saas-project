"use client"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { Branch, POStatus, Supplier } from "@/lib/types/purchase-orders"

interface POFiltersProps {
  status: string
  supplier: string
  branch: string
  search: string
  dateFrom: string
  dateTo: string
  suppliers: Supplier[]
  branches: Branch[]
  onFilterChange: (key: string, value: string) => void
}

const STATUS_OPTIONS: Array<{ label: string; value: POStatus }> = [
  { label: "Draft", value: "DRAFT" },
  { label: "Submitted", value: "SUBMITTED" },
  { label: "Partially Received", value: "PARTIALLY_RECEIVED" },
  { label: "Fully Received", value: "FULLY_RECEIVED" },
  { label: "Cancelled", value: "CANCELLED" },
]

export function POFilters({
  status,
  supplier,
  branch,
  search,
  dateFrom,
  dateTo,
  suppliers,
  branches,
  onFilterChange,
}: POFiltersProps) {
  return (
    <div className="grid gap-4 rounded-xl border border-border bg-card p-4 md:grid-cols-2 xl:grid-cols-6">
      <div className="space-y-2">
        <Label htmlFor="status">Status</Label>
        <select
          id="status"
          value={status}
          onChange={(event) => onFilterChange("status", event.target.value)}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="supplier">Supplier</Label>
        <select
          id="supplier"
          value={supplier}
          onChange={(event) => onFilterChange("supplier", event.target.value)}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
        >
          <option value="">All suppliers</option>
          {suppliers.map((option) => (
            <option key={option.id} value={String(option.id)}>
              {option.display_name}{option.is_active === false ? " (inactive)" : ""}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="branch">Branch</Label>
        <select
          id="branch"
          value={branch}
          onChange={(event) => onFilterChange("branch", event.target.value)}
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
        <Label htmlFor="search">PO number</Label>
        <Input
          id="search"
          value={search}
          placeholder="Search PO number"
          onChange={(event) => onFilterChange("search", event.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="dateFrom">Date from</Label>
        <Input
          id="dateFrom"
          type="date"
          value={dateFrom}
          onChange={(event) => onFilterChange("created_at_after", event.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="dateTo">Date to</Label>
        <Input
          id="dateTo"
          type="date"
          value={dateTo}
          onChange={(event) => onFilterChange("created_at_before", event.target.value)}
        />
      </div>
    </div>
  )
}
