"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

import { useAccessibleOrgs } from "@/lib/hooks/useAccessibleOrgs"
import { useAuth } from "@/lib/hooks/useAuth"
import { useOrg } from "@/lib/hooks/useOrg"

export function OrgAccessGuard({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const { user, isLoading } = useAuth()
  const { orgId } = useOrg()
  const { data: orgs = [], isLoading: orgsLoading } = useAccessibleOrgs(!!user)

  useEffect(() => {
    if (isLoading || orgsLoading || !user) return

    if (orgs.length === 0) {
      router.replace("/login")
      return
    }

    const hasAccess = orgs.some((org) => org.id === orgId)
    if (!hasAccess) {
      router.replace(`/orgs/${orgs[0].id}/dashboard`)
    }
  }, [user, isLoading, orgsLoading, orgs, orgId, router])

  if (isLoading || orgsLoading) {
    return null
  }

  if (!orgs.some((org) => org.id === orgId)) {
    return null
  }

  return <>{children}</>
}
