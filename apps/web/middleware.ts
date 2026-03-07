import { NextRequest, NextResponse } from "next/server"

function getTenantSubdomain(hostname: string): string | null {
  const parts = hostname.split(".")
  if (hostname === "localhost" || hostname === "127.0.0.1" || parts.length < 2) {
    return null
  }

  if (parts.length >= 2 && parts[parts.length - 1] === "localhost") {
    return parts[0] ?? null
  }

  return null
}

export function middleware(request: NextRequest) {
  const host = request.headers.get("host") ?? ""
  const hostname = host.split(":")[0] ?? ""
  const subdomain = getTenantSubdomain(hostname)

  const requestHeaders = new Headers(request.headers)
  requestHeaders.set("x-forwarded-host", hostname)
  if (subdomain) {
    requestHeaders.set("x-tenant-subdomain", subdomain)
  } else {
    requestHeaders.delete("x-tenant-subdomain")
  }

  return NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  })
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
}
