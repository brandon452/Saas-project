import type { ComponentType } from "react"
import {
  ArrowLeftRight,
  ClipboardCheck,
  LayoutDashboard,
  Package,
  Settings,
  ShoppingCart,
  Truck,
  Users,
} from "lucide-react"

export interface NavItem {
  label: string
  href: string
  icon: ComponentType<{ className?: string }>
  allowedRoles: Array<"OWNER" | "ADMIN" | "STAFF"> | "all"
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

export function getNavGroups(orgId: string): NavGroup[] {
  return [
    {
      label: "Inventory",
      items: [
        {
          label: "Dashboard",
          href: `/orgs/${orgId}/dashboard`,
          icon: LayoutDashboard,
          allowedRoles: "all",
        },
        {
          label: "Stock Levels",
          href: `/orgs/${orgId}/stock-levels`,
          icon: Package,
          allowedRoles: "all",
        },
      ],
    },
    {
      label: "Procurement",
      items: [
        {
          label: "Suppliers",
          href: `/orgs/${orgId}/suppliers`,
          icon: Truck,
          allowedRoles: ["OWNER", "ADMIN"],
        },
        {
          label: "Purchase Orders",
          href: `/orgs/${orgId}/purchase-orders`,
          icon: ShoppingCart,
          allowedRoles: ["OWNER", "ADMIN"],
        },
        {
          label: "Goods Receipts",
          href: `/orgs/${orgId}/goods-receipts`,
          icon: ClipboardCheck,
          allowedRoles: "all",
        },
        {
          label: "Branch Transfers",
          href: `/orgs/${orgId}/branch-transfers`,
          icon: ArrowLeftRight,
          allowedRoles: "all",
        },
      ],
    },
    {
      label: "Administration",
      items: [
        {
          label: "Users & Org Management",
          href: `/orgs/${orgId}/users`,
          icon: Users,
          allowedRoles: ["OWNER", "ADMIN"],
        },
        {
          label: "Settings",
          href: `/orgs/${orgId}/settings`,
          icon: Settings,
          allowedRoles: ["OWNER", "ADMIN"],
        },
      ],
    },
  ]
}
