import { apiRequest } from "@/lib/api"

export interface PaginatedResults<T> {
  count?: number
  next: string | null
  previous?: string | null
  results: T[]
}

export function toRelativePath(next: string): string {
  return next.replace(/^https?:\/\/[^/]+\/api\//, "")
}

type RequestFn = <T>(path: string, options?: RequestInit) => Promise<T>

export async function fetchAllPages<T>(
  firstPath: string,
  requestFn: RequestFn = apiRequest,
): Promise<T[]> {
  const results: T[] = []
  let nextPath: string | null = firstPath

  while (nextPath) {
    const response: PaginatedResults<T> = await requestFn<PaginatedResults<T>>(nextPath)
    results.push(...response.results)
    nextPath = response.next ? toRelativePath(response.next) : null
  }

  return results
}
