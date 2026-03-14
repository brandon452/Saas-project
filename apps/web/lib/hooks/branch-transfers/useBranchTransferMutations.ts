"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useRouter } from "next/navigation"

import { apiRequest } from "@/lib/api"
import { getCsrfHeader } from "@/lib/csrf"
import type {
  BranchTransfer,
  CreateTransferPayload,
  ReceiveTransferPayload,
} from "@/lib/types/branch-transfers"

export function useCreateTransfer(orgId: string) {
  const queryClient = useQueryClient()
  const router = useRouter()

  return useMutation({
    mutationFn: (payload: CreateTransferPayload) =>
      apiRequest<BranchTransfer>(`orgs/${orgId}/branch-transfers/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getCsrfHeader() },
        body: JSON.stringify(payload),
      }),
    onSuccess: (transfer) => {
      queryClient.invalidateQueries({ queryKey: ["branch-transfers", orgId] })
      router.push(`/orgs/${orgId}/branch-transfers/${transfer.id}`)
    },
  })
}

export function useApproveTransfer(orgId: string, transferId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () =>
      apiRequest<BranchTransfer>(`orgs/${orgId}/branch-transfers/${transferId}/approve/`, {
        method: "POST",
        headers: { ...getCsrfHeader() },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["branch-transfers", orgId, transferId],
      })
    },
  })
}

export function useDispatchTransfer(orgId: string, transferId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () =>
      apiRequest<BranchTransfer>(`orgs/${orgId}/branch-transfers/${transferId}/dispatch/`, {
        method: "POST",
        headers: { ...getCsrfHeader() },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["branch-transfers", orgId, transferId],
      })
    },
  })
}

export function useReceiveTransfer(orgId: string, transferId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: ReceiveTransferPayload) =>
      apiRequest<BranchTransfer>(`orgs/${orgId}/branch-transfers/${transferId}/receive/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getCsrfHeader() },
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["branch-transfers", orgId, transferId],
      })
    },
  })
}

export function useCancelTransfer(orgId: string, transferId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () =>
      apiRequest<BranchTransfer>(`orgs/${orgId}/branch-transfers/${transferId}/cancel/`, {
        method: "POST",
        headers: { ...getCsrfHeader() },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["branch-transfers", orgId, transferId],
      })
    },
  })
}
