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
    mutationFn: (data: { name: string }) =>
      apiRequest<Supplier>(`orgs/${orgId}/suppliers/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getCsrfHeader() },
        body: JSON.stringify(data),
      }),
    onSuccess: invalidate,
  })

  const updateSupplier = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      apiRequest<Supplier>(`orgs/${orgId}/suppliers/${id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...getCsrfHeader() },
        body: JSON.stringify({ name }),
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

  return { createSupplier, updateSupplier, deactivateSupplier }
}
