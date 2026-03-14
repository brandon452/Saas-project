import { Badge } from "@/components/ui/badge"
import type { ReceiptType } from "@/lib/types/goods-receipts"

const config: Record<ReceiptType, { label: string; variant: "default" | "secondary" }> = {
  PO_RECEIPT: { label: "PO Receipt", variant: "default" },
  DIRECT_RECEIPT: { label: "Direct Receipt", variant: "secondary" },
}

export function GoodsReceiptTypeBadge({ type }: { type: ReceiptType }) {
  const { label, variant } = config[type]

  return <Badge variant={variant}>{label}</Badge>
}
