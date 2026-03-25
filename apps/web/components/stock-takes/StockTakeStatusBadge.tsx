import { Badge } from "@/components/ui/badge"
import type { StockTakeStatus } from "@/lib/types/stock-takes"
import { getStockTakeStatusTone } from "@/lib/utils/stock-takes"

const LABELS: Record<StockTakeStatus, string> = {
  DRAFT: "Draft",
  IN_PROGRESS: "In Progress",
  PENDING_APPROVAL: "Pending Approval",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
}

export function StockTakeStatusBadge({ status }: { status: StockTakeStatus }) {
  return <Badge variant={getStockTakeStatusTone(status)}>{LABELS[status]}</Badge>
}
