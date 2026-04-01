"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { getCsrfHeader } from "@/lib/csrf"
import type { SupplierContact } from "@/lib/types/suppliers"

export function useSupplierContactMutations(orgId: string, supplierId: number) {
  const queryClient = useQueryClient()

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["supplier-contacts", orgId, supplierId] })
    queryClient.invalidateQueries({ queryKey: ["suppliers", orgId] })
  }

  const addContact = useMutation({
    mutationFn: (data: { full_name: string; role?: string; email?: string; phone?: string }) =>
      apiRequest<SupplierContact>(`orgs/${orgId}/suppliers/${supplierId}/contacts/add/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getCsrfHeader() },
        body: JSON.stringify(data),
      }),
    onSuccess: invalidate,
  })

  const updateContact = useMutation({
    mutationFn: ({
      contactId,
      data,
    }: {
      contactId: number
      data: Partial<{ full_name: string; role: string; email: string; phone: string }>
    }) =>
      apiRequest<SupplierContact>(
        `orgs/${orgId}/suppliers/${supplierId}/contacts/${contactId}/`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json", ...getCsrfHeader() },
          body: JSON.stringify(data),
        },
      ),
    onSuccess: invalidate,
  })

  const deactivateContact = useMutation({
    mutationFn: (contactId: number) =>
      apiRequest<SupplierContact>(
        `orgs/${orgId}/suppliers/${supplierId}/contacts/${contactId}/deactivate/`,
        {
          method: "PATCH",
          headers: getCsrfHeader(),
        },
      ),
    onSuccess: invalidate,
  })

  const reactivateContact = useMutation({
    mutationFn: (contactId: number) =>
      apiRequest<SupplierContact>(
        `orgs/${orgId}/suppliers/${supplierId}/contacts/${contactId}/reactivate/`,
        {
          method: "PATCH",
          headers: getCsrfHeader(),
        },
      ),
    onSuccess: invalidate,
  })

  const deleteContact = useMutation({
    mutationFn: (contactId: number) =>
      apiRequest<void>(
        `orgs/${orgId}/suppliers/${supplierId}/contacts/${contactId}/delete/`,
        {
          method: "DELETE",
          headers: getCsrfHeader(),
        },
      ),
    onSuccess: invalidate,
  })

  const setPrimaryContact = useMutation({
    mutationFn: (contactId: number) =>
      apiRequest<SupplierContact>(
        `orgs/${orgId}/suppliers/${supplierId}/contacts/${contactId}/set-primary/`,
        {
          method: "PATCH",
          headers: getCsrfHeader(),
        },
      ),
    onSuccess: invalidate,
  })

  return { addContact, updateContact, deactivateContact, reactivateContact, deleteContact, setPrimaryContact }
}
