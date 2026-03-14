import { getCsrfHeader } from "./csrf"

/**
 * isRefreshing prevents concurrent silent refresh loops.
 * If multiple requests return 401 simultaneously, only one
 * refresh attempt runs. This flag is intentional - do not remove it.
 */
let isRefreshing = false

const SAFE_METHODS = ["GET", "HEAD", "OPTIONS"]
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ""

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  orgId?: number | string,
  branchId?: number | string,
): Promise<T> {
  const cleanPath = path.startsWith("/") ? path.slice(1) : path
  const prefix = orgId ? `orgs/${orgId}/` : ""
  const url = `${API_BASE}/api/${prefix}${cleanPath}`

  const headers: Record<string, string> = {}
  const method = (options.method ?? "GET").toUpperCase()

  if (options.body) {
    headers["Content-Type"] = "application/json"
  }

  if (branchId) {
    headers["X-BRANCH-ID"] = String(branchId)
  }

  if (!SAFE_METHODS.includes(method)) {
    Object.assign(headers, getCsrfHeader())
  }

  const res = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      ...headers,
      ...(options.headers ?? {}),
    },
  })

  const refreshable = cleanPath !== "auth/refresh/" && cleanPath !== "auth/login/"

  if (res.status === 401 && refreshable && !isRefreshing) {
    isRefreshing = true
    try {
      const refreshed = await attemptTokenRefresh()
      if (refreshed) {
        isRefreshing = false
        return apiRequest<T>(path, options, orgId, branchId)
      }
    } catch {
      // fall through
    }
    isRefreshing = false
    redirectToLogin()
    throw new Error("Session expired.")
  }

  if (res.status === 401 && refreshable && isRefreshing) {
    redirectToLogin()
    throw new Error("Session expired.")
  }

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`)
  }

  if (res.status === 204) {
    return undefined as T
  }

  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

async function attemptTokenRefresh(): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/auth/refresh/`, {
    method: "POST",
    credentials: "include",
    headers: {
      ...getCsrfHeader(),
    },
  })
  return res.ok
}

function redirectToLogin(): void {
  if (typeof window !== "undefined") {
    window.location.href = "/login"
  }
}
