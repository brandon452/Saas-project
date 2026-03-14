import { Badge } from "@/components/ui/badge"
import type { POStatus } from "@/lib/types/purchase-orders"

const STATUS_CONFIG: Record<
  POStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  DRAFT: { label: "Draft", variant: "secondary" },
  SUBMITTED: { label: "Submitted", variant: "default" },
  PARTIALLY_RECEIVED: { label: "Partially Received", variant: "outline" },
  FULLY_RECEIVED: { label: "Fully Received", variant: "default" },
  CANCELLED: { label: "Cancelled", variant: "destructive" },
}

export function POStatusBadge({ status }: { status: POStatus }) {
  const config = STATUS_CONFIG[status] ?? {
    label: status,
    variant: "secondary" as const,
  }

  return <Badge variant={config.variant}>{config.label}</Badge>
}
