"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api"
import { fetchAllPages } from "@/lib/utils/pagination"
import type { ParentMember } from "@/lib/types/parent"

export function useParentMembers() {
  return useQuery<ParentMember[]>({
    queryKey: ["parent", "members"],
    queryFn: () => fetchAllPages<ParentMember>("parent/members/", apiRequest),
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
}
