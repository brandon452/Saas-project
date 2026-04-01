"use client"

import { useMutation, useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { getCsrfHeader } from "@/lib/csrf"

export interface CreateUserPayload {
  email: string
  first_name: string
  last_name: string
  role: string
  assigned_branch?: string | null
}

export interface CreateUserResult {
  user_id: string
  email: string
  set_password_url: string
}

export interface PasswordSetTokenDetail {
  email: string
  first_name: string
  org_name: string | null
  parent_role: string | null
}

export interface SetPasswordPayload {
  password: string
}

export function useCreateUser(orgId: string) {
  return useMutation({
    mutationFn: (payload: CreateUserPayload) =>
      apiRequest<CreateUserResult>(`orgs/${orgId}/create-user/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getCsrfHeader(),
        },
        body: JSON.stringify(payload),
      }),
  })
}

export function usePasswordSetTokenDetail(token: string) {
  return useQuery<PasswordSetTokenDetail>({
    queryKey: ["set-password", token],
    queryFn: () => apiRequest<PasswordSetTokenDetail>(`auth/set-password/${token}/`),
    retry: false,
    enabled: !!token,
  })
}

export function useSetPassword(token: string) {
  return useMutation({
    mutationFn: (payload: SetPasswordPayload) =>
      apiRequest<{ detail: string }>(`auth/set-password/${token}/accept/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
  })
}
