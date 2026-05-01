"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import type { PaginatedResponse, PurchaseOrder } from "@/lib/types/purchase-orders"

interface UsePurchaseOrdersParams {
  orgId: string
  page?: number
  status?: string
  supplier?: number
  branch?: number
  search?: string
  dateFrom?: string
  dateTo?: string
}

export function usePurchaseOrders(params: UsePurchaseOrdersParams) {
  const { orgId, page = 1, status, supplier, branch, search, dateFrom, dateTo } = params

  const searchParams = new URLSearchParams()
  searchParams.set("page", String(page))
  if (status) searchParams.set("status", status)
  if (supplier) searchParams.set("supplier", String(supplier))
  if (branch) searchParams.set("branch", String(branch))
  if (search) searchParams.set("search", search)
  if (dateFrom) searchParams.set("created_at_after", dateFrom)
  if (dateTo) searchParams.set("created_at_before", dateTo)

  return useQuery<PaginatedResponse<PurchaseOrder>>({
    queryKey: [
      "purchase-orders",
      orgId,
      page,
      status,
      supplier,
      branch,
      search,
      dateFrom,
      dateTo,
    ],
    queryFn: () =>
      apiRequest<PaginatedResponse<PurchaseOrder>>(
        `orgs/${orgId}/purchase-orders/?${searchParams.toString()}`,
    ),
    enabled: !!orgId,
    staleTime: 30 * 1000,
    placeholderData: (previousData) => previousData,
  })
}
