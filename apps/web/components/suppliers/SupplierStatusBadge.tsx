import { Badge } from "@/components/ui/badge"

export function SupplierStatusBadge({ isActive }: { isActive: boolean }) {
  return isActive ? (
    <Badge variant="default">Active</Badge>
  ) : (
    <Badge variant="secondary">Inactive</Badge>
  )
}
