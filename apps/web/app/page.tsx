"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

import { useAccessibleOrgs } from "@/lib/hooks/useAccessibleOrgs"
import { useAuth } from "@/lib/hooks/useAuth"

export default function RootPage() {
  const router = useRouter()
  const { user, isLoading } = useAuth()
  const { data: orgs = [], isLoading: orgsLoading } = useAccessibleOrgs(!!user)

  useEffect(() => {
    if (isLoading) return

    if (!user) {
      router.replace("/login")
      return
    }

    if (orgsLoading) return

    if (orgs.length > 0) {
      router.replace(`/orgs/${orgs[0].id}/dashboard`)
      return
    }

    router.replace("/login")
  }, [user, isLoading, orgs, orgsLoading, router])

  return null
}
