import type { POLine } from "@/lib/types/purchase-orders"

export function calculatePOTotal(lines: POLine[]): number {
  return lines.reduce(
    (sum, line) => sum + line.ordered_quantity * parseFloat(line.unit_price),
    0,
  )
}

export function formatPOValue(value: number): string {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}
