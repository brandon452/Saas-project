"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { ChevronUp, LogOut } from "lucide-react"

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
import { getCsrfHeader } from "@/lib/csrf"
import { useAuth } from "@/lib/hooks/useAuth"
import { getParentNavGroups } from "@/lib/nav"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ""

export function ParentSidebar() {
  const { user } = useAuth()
  const { collapsed } = useSidebar()
  const pathname = usePathname()
  const navGroups = getParentNavGroups()

  async function handleLogout() {
    await fetch(`${API_BASE}/api/auth/logout/`, {
      method: "POST",
      credentials: "include",
      headers: {
        ...getCsrfHeader(),
      },
    })
    window.location.href = "/login"
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
      </SidebarHeader>

      <SidebarContent>
        {navGroups.map((group) => (
          <SidebarGroup key={group.label}>
            <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
            <SidebarMenu>
              {group.items.map((item) => {
                const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`)

                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton asChild isActive={isActive} tooltip={item.label}>
                      <Link href={item.href} title={collapsed ? item.label : undefined}>
                        <item.icon className="h-4 w-4" />
                        {!collapsed ? <span>{item.label}</span> : null}
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter>
        <SidebarSeparator />
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
            <DropdownMenuItem onClick={handleLogout} className="gap-2">
              <LogOut className="h-4 w-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
