import { Badge } from "@/components/ui/badge"
import type { QuickSaleStatus } from "@/lib/types/quick-sales"

export function QuickSaleStatusBadge({ status }: { status: QuickSaleStatus }) {
  if (status === "CONFIRMED") {
    return <Badge variant="default">Confirmed</Badge>
  }

  return <Badge variant="secondary">Voided</Badge>
}
