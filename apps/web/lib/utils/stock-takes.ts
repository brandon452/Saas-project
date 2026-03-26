import type { Branch } from "@/lib/types/purchase-orders"
import type { StockTakeStatus } from "@/lib/types/stock-takes"

export function formatQuantity(value: string | null | undefined): string {
  if (value == null || value === "") return "\u2014"
  const n = Number(value)
  return Number.isFinite(n) ? n.toString() : value
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "\u2014"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "\u2014"
  return date.toLocaleString()
}

export function getStockTakeStatusTone(
  status: StockTakeStatus,
): "secondary" | "default" | "outline" | "destructive" {
  switch (status) {
    case "DRAFT":
      return "secondary"
    case "IN_PROGRESS":
      return "default"
    case "PENDING_APPROVAL":
      return "outline"
    case "COMPLETED":
      return "secondary"
    case "COMPLETED_WITH_VARIANCES":
      return "default"
    case "CANCELLED":
      return "destructive"
    default:
      return "outline"
  }
}

export function canEditNotes(status: StockTakeStatus): boolean {
  return status === "DRAFT" || status === "IN_PROGRESS"
}

export function canEditLines(status: StockTakeStatus): boolean {
  return status === "IN_PROGRESS"
}

export function getStockTakeBranchLabel(
  branch: string | { id: string; name?: string; code?: string },
  branches?: Branch[],
): string {
  if (typeof branch !== "string") {
    return branch.name || branch.code || branch.id
  }

  const match = branches?.find((candidate) => String(candidate.id) === branch)
  return match?.name || branch
}
