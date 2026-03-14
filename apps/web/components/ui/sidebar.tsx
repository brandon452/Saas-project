"use client"

import * as React from "react"
import { PanelLeftClose, PanelLeftOpen } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

type SidebarContextValue = {
  collapsed: boolean
  setCollapsed: React.Dispatch<React.SetStateAction<boolean>>
}

const SidebarContext = React.createContext<SidebarContextValue | null>(null)

function useSidebarContext() {
  const context = React.useContext(SidebarContext)
  if (!context) {
    throw new Error("Sidebar components must be used within SidebarProvider")
  }
  return context
}

export function useSidebar() {
  return useSidebarContext()
}

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = React.useState(false)

  return (
    <SidebarContext.Provider value={{ collapsed, setCollapsed }}>
      {children}
    </SidebarContext.Provider>
  )
}

export function Sidebar({
  children,
  className,
}: {
  children: React.ReactNode
  collapsible?: "icon"
  className?: string
}) {
  const { collapsed } = useSidebarContext()

  return (
    <aside
      data-collapsible={collapsed ? "icon" : ""}
      className={cn(
        "group flex h-screen shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-[width]",
        collapsed ? "w-20" : "w-72",
        className,
      )}
    >
      {children}
    </aside>
  )
}

export function SidebarTrigger({ className }: { className?: string }) {
  const { collapsed, setCollapsed } = useSidebarContext()

  return (
    <Button
      variant="ghost"
      className={cn("h-8 w-8 px-0", className)}
      onClick={() => setCollapsed((value) => !value)}
      aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
    >
      {collapsed ? (
        <PanelLeftOpen className="h-4 w-4" />
      ) : (
        <PanelLeftClose className="h-4 w-4" />
      )}
    </Button>
  )
}

export function SidebarHeader({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  const { collapsed } = useSidebarContext()

  return <div className={cn(collapsed ? "p-2" : "p-3", className)}>{children}</div>
}

export function SidebarContent({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  const { collapsed } = useSidebarContext()

  return (
    <div className={cn("flex-1 overflow-y-auto pb-3", collapsed ? "px-2" : "px-3", className)}>
      {children}
    </div>
  )
}

export function SidebarFooter({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  const { collapsed } = useSidebarContext()

  return <div className={cn(collapsed ? "p-2" : "p-3", className)}>{children}</div>
}

export function SidebarGroup({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return <section className={cn("mt-4", className)}>{children}</section>
}

export function SidebarGroupLabel({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  const { collapsed } = useSidebarContext()

  if (collapsed) return null

  return (
    <div
      className={cn(
        "mb-2 px-2 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground",
        className,
      )}
    >
      {children}
    </div>
  )
}

export function SidebarMenu({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return <div className={cn("flex flex-col gap-1", className)}>{children}</div>
}

export function SidebarMenuItem({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return <div className={className}>{children}</div>
}

export function SidebarMenuButton({
  children,
  asChild,
  isActive,
  className,
}: {
  children: React.ReactNode
  asChild?: boolean
  isActive?: boolean
  tooltip?: string
  className?: string
}) {
  const { collapsed } = useSidebarContext()
  const classes = cn(
    "flex w-full items-center rounded-md py-2 text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
    collapsed ? "justify-center px-0" : "gap-3 px-2",
    isActive && "bg-sidebar-primary text-sidebar-primary-foreground hover:bg-sidebar-primary hover:text-sidebar-primary-foreground",
    className,
  )

  if (asChild && React.isValidElement(children)) {
    const child = children as React.ReactElement<{ className?: string }>
    return React.cloneElement(child, {
      className: cn(classes, child.props.className),
    })
  }

  return <button className={classes}>{children}</button>
}

export function SidebarSeparator() {
  return <Separator className="my-3 bg-sidebar-border" />
}
