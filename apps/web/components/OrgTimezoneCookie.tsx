"use client"

import { useEffect } from "react"

import { useOrg } from "@/lib/hooks/useOrg"
import { useOrgSettings } from "@/lib/hooks/useOrgSettings"

export function OrgTimezoneCookie() {
  const { orgId } = useOrg()
  const settingsQuery = useOrgSettings(orgId)

  useEffect(() => {
    const tz = settingsQuery.data?.default_timezone
    if (!orgId || !tz) return
    const next = `${orgId}:${tz}`
    const current =
      document.cookie
        .split("; ")
        .find((c) => c.startsWith("org_tz="))
        ?.split("=")[1] ?? ""
    if (current !== next) {
      const secure = location.protocol === "https:" ? "; Secure" : ""
      document.cookie = `org_tz=${next}; path=/; SameSite=Lax; Max-Age=2592000${secure}`
    }
  }, [orgId, settingsQuery.data?.default_timezone])

  return null
}
