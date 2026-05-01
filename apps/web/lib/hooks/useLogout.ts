"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useRouter } from "next/navigation"

import { apiRequest, setLogoutInProgress } from "@/lib/api"

export function useLogout() {
  const queryClient = useQueryClient()
  const router = useRouter()

  return useMutation({
    mutationFn: async () => {
      setLogoutInProgress(true)
      await queryClient.cancelQueries()
      return apiRequest("auth/logout/", { method: "POST" })
    },
    onSuccess: async () => {
      queryClient.removeQueries()
      router.replace("/login")
      router.refresh()
    },
    onError: () => {
      setLogoutInProgress(false)
    },
  })
}
