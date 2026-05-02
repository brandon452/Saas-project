"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { AuditEventListResponse } from "@/lib/types/audit-events"

export interface AuditEventFilters {
  event_type?: string
  resource_id?: string
  q?: string
  from?: string
  to?: string
  changed_by_me?: boolean
  actor_user_id?: string
}

export function useAuditEvents(orgId: string, filters: AuditEventFilters) {
  return useQuery<AuditEventListResponse>({
    queryKey: ["audit-events", orgId, filters],
    enabled: !!orgId,
    queryFn: () => {
      const params = new URLSearchParams()
      if (filters.event_type) params.set("event_type", filters.event_type)
      if (filters.resource_id) params.set("resource_id", filters.resource_id)
      if (filters.q) params.set("q", filters.q)
      if (filters.from) params.set("from", filters.from)
      if (filters.to) params.set("to", filters.to)
      if (filters.changed_by_me && filters.actor_user_id) params.set("actor_user_id", filters.actor_user_id)

      const query = params.toString()
      const path = query ? `orgs/${orgId}/audit-events/?${query}` : `orgs/${orgId}/audit-events/`
      return apiRequest<AuditEventListResponse>(path)
    },
    placeholderData: (prev) => prev,
  })
}
