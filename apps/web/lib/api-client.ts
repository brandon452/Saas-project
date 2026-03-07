function getBrowserHostNoPort(): string {
  return window.location.hostname
}

async function getHostNoPort(): Promise<string> {
  if (typeof window !== "undefined") {
    return getBrowserHostNoPort()
  }

  const { headers } = await import("next/headers")
  const host = headers().get("x-forwarded-host") ?? headers().get("host") ?? ""
  return host.split(":")[0] ?? "localhost"
}

async function getApiBaseUrl(): Promise<string> {
  const envBase = process.env.NEXT_PUBLIC_API_URL
  if (envBase) return envBase

  const host = await getHostNoPort()
  return `http://${host}:8000`
}

export async function apiRequest(path: string, options: RequestInit = {}): Promise<Response> {
  const baseUrl = await getApiBaseUrl()
  return fetch(`${baseUrl}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  })
}
