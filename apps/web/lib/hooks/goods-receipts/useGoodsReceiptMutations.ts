"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useRouter } from "next/navigation"

import { apiRequest } from "@/lib/api"
import { getCsrfHeader } from "@/lib/csrf"
import type {
  CreateDirectReceiptPayload,
  CreatePOReceiptPayload,
  GoodsReceipt,
} from "@/lib/types/goods-receipts"

export function useCreateGoodsReceipt(orgId: string) {
  const queryClient = useQueryClient()
  const router = useRouter()

  return useMutation({
    mutationFn: (payload: CreatePOReceiptPayload | CreateDirectReceiptPayload) =>
      apiRequest<GoodsReceipt>(`orgs/${orgId}/goods-receipts/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getCsrfHeader() },
        body: JSON.stringify(payload),
      }),
    onSuccess: (receipt) => {
      queryClient.invalidateQueries({ queryKey: ["goods-receipts", orgId] })
      router.push(`/orgs/${orgId}/goods-receipts/${receipt.id}`)
    },
  })
}
