import type { ComponentType } from "react"
import {
  AlertTriangle,
  ArrowLeftRight,
  BarChart3,
  BookOpen,
  Building2,
  ClipboardCheck,
  ClipboardList,
  Clock,
  History,
  LayoutDashboard,
  Layers,
  LockKeyhole,
  Package,
  Settings,
  SlidersHorizontal,
  ShoppingCart,
  Receipt,
  Tag,
  TrendingUp,
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
          label: "Item Catalog",
          href: `/orgs/${orgId}/inventory/items`,
          icon: Tag,
          allowedRoles: "all",
        },
        {
          label: "Branch Items",
          href: `/orgs/${orgId}/branch-items`,
          icon: Layers,
          allowedRoles: "all",
        },
        {
          label: "Stock Levels",
          href: `/orgs/${orgId}/stock`,
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
          label: "Quick Sales",
          href: `/orgs/${orgId}/quick-sales`,
          icon: Receipt,
          allowedRoles: "all",
        },
        {
          label: "Branch Transfers",
          href: `/orgs/${orgId}/branch-transfers`,
          icon: ArrowLeftRight,
          allowedRoles: "all",
        },
        {
          label: "Stock Takes",
          href: `/orgs/${orgId}/stock-takes`,
          icon: ClipboardList,
          allowedRoles: "all",
        },
        {
          label: "Stock Adjustments",
          href: `/orgs/${orgId}/stock-adjustments`,
          icon: SlidersHorizontal,
          allowedRoles: "all",
        },
        {
          label: "Stock Movements",
          href: `/orgs/${orgId}/stock-movements`,
          icon: History,
          allowedRoles: "all",
        },
      ],
    },
    {
      label: "Administration",
      items: [
        {
          label: "Users",
          href: `/orgs/${orgId}/users`,
          icon: Users,
          allowedRoles: ["OWNER", "ADMIN"],
        },
        {
          label: "Branches",
          href: `/orgs/${orgId}/branches`,
          icon: Building2,
          allowedRoles: ["OWNER", "ADMIN"],
        },
        {
          label: "Close Periods",
          href: `/orgs/${orgId}/close-periods`,
          icon: LockKeyhole,
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
    {
      label: "Reports",
      items: [
        {
          label: "Cost Trend",
          href: `/orgs/${orgId}/reports/cost-trend`,
          icon: TrendingUp,
          allowedRoles: ["OWNER", "ADMIN"],
        },
        {
          label: "Stock Valuation",
          href: `/orgs/${orgId}/reports/stock-valuation`,
          icon: BarChart3,
          allowedRoles: ["OWNER", "ADMIN"],
        },
        {
          label: "Inventory Aging",
          href: `/orgs/${orgId}/reports/inventory-aging`,
          icon: Clock,
          allowedRoles: ["OWNER", "ADMIN"],
        },
        {
          label: "Slow / Dead Stock",
          href: `/orgs/${orgId}/reports/slow-dead-stock`,
          icon: AlertTriangle,
          allowedRoles: ["OWNER", "ADMIN"],
        },
      ],
    },
  ]
}

export function getParentNavGroups(): NavGroup[] {
  return [
    {
      label: "Network",
      items: [
        {
          label: "Organizations",
          href: "/parent/organizations",
          icon: Building2,
          allowedRoles: "all",
        },
        {
          label: "Global Catalog",
          href: "/parent/master-items",
          icon: BookOpen,
          allowedRoles: "all",
        },
        {
          label: "Parent Users",
          href: "/parent/users",
          icon: Users,
          allowedRoles: "all",
        },
      ],
    },
  ]
}
