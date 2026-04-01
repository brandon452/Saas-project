"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { getCsrfHeader } from "@/lib/csrf"
import type { Supplier } from "@/lib/types/suppliers"

export function useSupplierMutations(orgId: string) {
  const queryClient = useQueryClient()

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["suppliers", orgId] })
  }

  const createSupplier = useMutation({
    mutationFn: (data: { display_name: string }) =>
      apiRequest<Supplier>(`orgs/${orgId}/suppliers/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getCsrfHeader() },
        body: JSON.stringify(data),
      }),
    onSuccess: invalidate,
  })

  const updateSupplier = useMutation({
    mutationFn: ({ id, data }: {
      id: number
      data: {
        display_name: string
        legal_name?: string
        email?: string
        phone?: string
        payment_terms_days?: number | null
        default_lead_time_days?: number | null
        currency?: string
        tax_id?: string
        address_line1?: string
        address_line2?: string
        city?: string
        state?: string
        postal_code?: string
        country?: string
        notes?: string
      }
    }) =>
      apiRequest<Supplier>(`orgs/${orgId}/suppliers/${id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...getCsrfHeader() },
        body: JSON.stringify(data),
      }),
    onSuccess: invalidate,
  })

  const deactivateSupplier = useMutation({
    mutationFn: (id: number) =>
      apiRequest<Supplier>(`orgs/${orgId}/suppliers/${id}/deactivate/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...getCsrfHeader() },
        body: JSON.stringify({ is_active: false }),
      }),
    onSuccess: invalidate,
  })

  const reactivateSupplier = useMutation({
    mutationFn: (id: number) =>
      apiRequest<Supplier>(`orgs/${orgId}/suppliers/${id}/reactivate/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...getCsrfHeader() },
        body: JSON.stringify({ is_active: true }),
      }),
    onSuccess: invalidate,
  })

  return { createSupplier, updateSupplier, deactivateSupplier, reactivateSupplier }
}
