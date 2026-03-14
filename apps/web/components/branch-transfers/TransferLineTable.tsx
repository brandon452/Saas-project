import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"
import type { BranchTransfer, TransferStatus } from "@/lib/types/branch-transfers"

function truncateUuid(value: string | null | undefined) {
  if (!value) return "\u2014"
  return `${value.slice(0, 8)}...`
}

function isReceivedStatus(status: TransferStatus) {
  return status === "RECEIVED_COMPLETE" || status === "RECEIVED_WITH_VARIANCE"
}

export function TransferLineTable({ transfer }: { transfer: BranchTransfer }) {
  const showReceivedColumns = isReceivedStatus(transfer.status)

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Item</TableHead>
          <TableHead>Qty Sent</TableHead>
          {showReceivedColumns ? <TableHead>Qty Received</TableHead> : null}
          {showReceivedColumns ? <TableHead>Variance</TableHead> : null}
        </TableRow>
      </TableHeader>
      <TableBody>
        {transfer.lines.map((line) => {
          const variance = (line.quantity_received ?? 0) - line.quantity_sent
          const varianceLabel = variance > 0 ? `+${variance}` : String(variance)

          return (
            <TableRow key={line.id}>
              <TableCell className="font-mono text-sm">{truncateUuid(line.item)}</TableCell>
              <TableCell>{line.quantity_sent}</TableCell>
              {showReceivedColumns ? <TableCell>{line.quantity_received ?? 0}</TableCell> : null}
              {showReceivedColumns ? (
                <TableCell className={cn(variance < 0 ? "text-red-600" : "")}>
                  {varianceLabel}
                </TableCell>
              ) : null}
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
