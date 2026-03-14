import { Badge } from "@/components/ui/badge"
import type { TransferStatus } from "@/lib/types/branch-transfers"

const config: Record<
  TransferStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  DRAFT: { label: "Draft", variant: "secondary" },
  APPROVED: { label: "Approved", variant: "default" },
  IN_TRANSIT: { label: "In Transit", variant: "default" },
  RECEIVED_COMPLETE: { label: "Received", variant: "default" },
  RECEIVED_WITH_VARIANCE: { label: "Received (Variance)", variant: "destructive" },
  CANCELLED: { label: "Cancelled", variant: "outline" },
}

export function BranchTransferStatusBadge({ status }: { status: TransferStatus }) {
  const { label, variant } = config[status]

  return <Badge variant={variant}>{label}</Badge>
}
