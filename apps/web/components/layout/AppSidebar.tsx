"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { ChevronUp, LogOut, Network } from "lucide-react"

import { OrgSwitcher } from "./OrgSwitcher"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar"
import { useAuth } from "@/lib/hooks/useAuth"
import { useLogout } from "@/lib/hooks/useLogout"
import { useOrg } from "@/lib/hooks/useOrg"
import { getNavGroups } from "@/lib/nav"

export function AppSidebar() {
  const { user } = useAuth()
  const logout = useLogout()
  const { orgId, role, isParentUser } = useOrg()
  const { collapsed, setCollapsed } = useSidebar()
  const pathname = usePathname()

  const navGroups = getNavGroups(orgId)

  function isNavItemVisible(allowedRoles: "all" | Array<"OWNER" | "ADMIN" | "STAFF">) {
    if (allowedRoles === "all") return true
    if (isParentUser) return true
    if (!role) return false
    return allowedRoles.includes(role)
  }

  async function handleLogout() {
    logout.mutate()
  }

  function handleNavClick() {
    if (window.matchMedia("(max-width: 767px)").matches) {
      setCollapsed(true)
    }
  }

  const firstInitial = user?.first_name?.[0] ?? ""
  const lastInitial = user?.last_name?.[0] ?? ""
  const initials = `${firstInitial}${lastInitial}`.toUpperCase() || "?"

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-1">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
            S
          </div>
          {!collapsed ? <span className="text-sm font-semibold tracking-tight">Symbiosis</span> : null}
        </div>
        <SidebarSeparator />
        {!collapsed ? <OrgSwitcher /> : null}
        {isParentUser ? (
          <SidebarMenu className="mt-2">
            <SidebarMenuItem>
              <SidebarMenuButton asChild tooltip="Parent Console">
                <Link href="/parent/organizations" title={collapsed ? "Parent Console" : undefined} onClick={handleNavClick}>
                  <Network className="h-4 w-4" />
                  {!collapsed ? <span>Parent Console</span> : null}
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        ) : null}
      </SidebarHeader>

      <SidebarContent>
        {navGroups.map((group) => {
          const visibleItems = group.items.filter((item) => isNavItemVisible(item.allowedRoles))

          if (visibleItems.length === 0) return null

          return (
            <SidebarGroup key={group.label}>
              <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
              <SidebarMenu>
                {visibleItems.map((item) => {
                  const isActive =
                    pathname === item.href || pathname.startsWith(`${item.href}/`)

                  return (
                    <SidebarMenuItem key={item.href}>
                      <SidebarMenuButton asChild isActive={isActive} tooltip={item.label}>
                        <Link href={item.href} title={collapsed ? item.label : undefined} onClick={handleNavClick}>
                          <item.icon className="h-4 w-4" />
                          {!collapsed ? <span>{item.label}</span> : null}
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </SidebarGroup>
          )
        })}
      </SidebarContent>

      <SidebarFooter>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton className="w-full">
              <Avatar className="h-6 w-6">
                <AvatarFallback className="text-xs">{initials}</AvatarFallback>
              </Avatar>
              {!collapsed ? (
                <>
                  <div className="flex min-w-0 flex-col text-left">
                    <span className="truncate text-sm font-medium">
                      {user?.first_name} {user?.last_name}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">{user?.email}</span>
                  </div>
                  <ChevronUp className="ml-auto h-4 w-4" />
                </>
              ) : null}
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-56">
            <DropdownMenuItem onClick={handleLogout} disabled={logout.isPending} className="gap-2">
              <LogOut className="h-4 w-4" />
              {logout.isPending ? "Signing out..." : "Sign out"}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
