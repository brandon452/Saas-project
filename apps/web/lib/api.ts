import { getCsrfHeader } from "./csrf"

/**
 * refreshPromise coordinates concurrent silent refresh attempts.
 * If multiple requests return 401 simultaneously, they all await
 * the same refresh request before retrying.
 */
let refreshPromise: Promise<boolean> | null = null
let logoutInProgress = false

const SAFE_METHODS = ["GET", "HEAD", "OPTIONS"]
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ""

export class ApiError extends Error {
  status: number
  data: unknown

  constructor(status: number, data: unknown, fallbackMessage?: string) {
    super(fallbackMessage ?? `API error: ${status}`)
    this.name = "ApiError"
    this.status = status
    this.data = data
  }
}

export function getApiErrorDetail(error: unknown): string | string[] | null {
  if (!(error instanceof ApiError) || !error.data || typeof error.data !== "object") {
    return null
  }

  if ("detail" in error.data) {
    const detail = (error.data as { detail?: unknown }).detail
    if (typeof detail === "string" || Array.isArray(detail)) {
      return detail as string | string[]
    }
  }

  return null
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  const detail = getApiErrorDetail(error)
  if (Array.isArray(detail)) {
    return detail.join(" ")
  }
  if (typeof detail === "string") {
    return detail
  }
  if (error instanceof ApiError && error.status === 403) {
    return "You do not have permission to perform this action."
  }
  return fallback
}

export function setLogoutInProgress(value: boolean): void {
  logoutInProgress = value
}

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

  if (logoutInProgress && cleanPath !== "auth/logout/" && cleanPath !== "auth/login/") {
    throw new ApiError(401, { detail: "Logout in progress." }, "Logout in progress.")
  }

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

  if (res.status === 401 && refreshable && !logoutInProgress) {
    const refreshed = await getRefreshPromise()
    if (refreshed) {
      return apiRequest<T>(path, options, orgId, branchId)
    }
    redirectToLogin()
    throw new Error("Session expired.")
  }

  const text = await res.text()
  let data: unknown
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      throw new ApiError(res.status, { detail: "Invalid server response" }, "Invalid server response")
    }
  } else {
    data = undefined
  }

  if (!res.ok) {
    throw new ApiError(res.status, data)
  }

  if (cleanPath === "auth/login/") {
    setLogoutInProgress(false)
  }

  if (res.status === 204) {
    return undefined as T
  }

  return data as T
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

async function getRefreshPromise(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = attemptTokenRefresh().catch(() => false)
    refreshPromise.finally(() => {
      refreshPromise = null
    })
  }

  return refreshPromise
}

function redirectToLogin(): void {
  if (typeof window !== "undefined") {
    window.location.href = "/login"
  }
}
