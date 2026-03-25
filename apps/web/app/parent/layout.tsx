"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

import { ParentSidebar } from "@/components/layout/ParentSidebar"
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { useAuth } from "@/lib/hooks/useAuth"

export default function ParentLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { user, isLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (isLoading) return

    if (!user) {
      router.replace("/login")
      return
    }

    if (!user.is_parent_member) {
      const firstOrg = user.memberships?.[0]?.org_id
      router.replace(firstOrg ? `/orgs/${firstOrg}/dashboard` : "/login")
    }
  }, [user, isLoading, router])

  if (isLoading || !user?.is_parent_member) {
    return null
  }

  return (
    <SidebarProvider>
      <div className="flex h-screen w-full overflow-hidden">
        <ParentSidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <header className="flex h-12 shrink-0 items-center gap-2 border-b border-border bg-card/80 px-4 backdrop-blur">
            <SidebarTrigger className="-ml-1" />
          </header>
          <main className="flex-1 overflow-y-auto p-6">{children}</main>
        </div>
      </div>
    </SidebarProvider>
  )
}
