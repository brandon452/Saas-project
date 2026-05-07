import { OrgAccessGuard } from "@/components/auth/OrgAccessGuard"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { AppSidebar } from "@/components/layout/AppSidebar"
import { OrgTimezoneCookie } from "@/components/OrgTimezoneCookie"
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"

export default function OrgLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <ProtectedRoute>
      <SidebarProvider>
        <div className="flex h-dvh w-full overflow-hidden">
          <AppSidebar />
          <div className="flex flex-1 flex-col overflow-hidden">
            <header className="flex h-12 shrink-0 items-center gap-2 border-b border-border bg-card/80 px-4 backdrop-blur">
              <SidebarTrigger className="-ml-1" />
            </header>
            <main className="flex-1 overflow-y-auto p-6">
              <OrgAccessGuard>{children}</OrgAccessGuard>
              <OrgTimezoneCookie />
            </main>
          </div>
        </div>
      </SidebarProvider>
    </ProtectedRoute>
  )
}
