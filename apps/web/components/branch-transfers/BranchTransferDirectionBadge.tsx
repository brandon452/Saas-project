import { Badge } from "@/components/ui/badge"
import type {
  BranchTransfer,
  BranchTransferListItem,
  TransferDirection,
} from "@/lib/types/branch-transfers"

interface Props {
  transfer: BranchTransferListItem | BranchTransfer
  orgId: string
}

const directionConfig: Record<
  TransferDirection,
  { label: string; variant: "default" | "secondary" | "outline" }
> = {
  Outbound: { label: "Outbound", variant: "default" },
  Inbound: { label: "Inbound", variant: "secondary" },
  Internal: { label: "Internal", variant: "outline" },
}

export function getTransferDirection(
  transfer: BranchTransferListItem | BranchTransfer,
  orgId: string,
): TransferDirection {
  return transfer.organization === orgId && transfer.to_organization === orgId
    ? "Internal"
    : transfer.organization === orgId
      ? "Outbound"
      : "Inbound"
}

export function BranchTransferDirectionBadge({ transfer, orgId }: Props) {
  const direction = getTransferDirection(transfer, orgId)
  const { label, variant } = directionConfig[direction]

  return <Badge variant={variant}>{label}</Badge>
}
