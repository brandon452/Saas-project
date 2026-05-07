import type { NextRequest } from "next/server"
import { NextResponse } from "next/server"

import { currentMonthStart } from "@/lib/utils/dates"

const DATE_DEFAULTS: Array<{ pattern: RegExp; param: string }> = [
  { pattern: /^\/orgs\/[^/]+\/goods-receipts$/, param: "date_after" },
  { pattern: /^\/orgs\/[^/]+\/purchase-orders$/, param: "created_at_after" },
  { pattern: /^\/orgs\/[^/]+\/stock-movements$/, param: "from_date" },
  { pattern: /^\/orgs\/[^/]+\/quick-sales$/, param: "from_date" },
]

function resolveOrgTimezone(request: NextRequest, orgId: string): string | undefined {
  const raw = request.cookies.get("org_tz")?.value ?? ""
  const colonIndex = raw.indexOf(":")
  if (colonIndex === -1) return undefined
  const storedOrgId = raw.slice(0, colonIndex)
  const timezone = raw.slice(colonIndex + 1)
  return storedOrgId === orgId && timezone ? timezone : undefined
}

export function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl

  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname === "/favicon.ico"
  ) {
    return NextResponse.next()
  }

  if (searchParams.toString() === "") {
    for (const { pattern, param } of DATE_DEFAULTS) {
      if (pattern.test(pathname)) {
        const orgId = pathname.split("/")[2] ?? ""
        if (!orgId) return NextResponse.next()
        const timezone = resolveOrgTimezone(request, orgId)
        const url = request.nextUrl.clone()
        url.hash = request.nextUrl.hash
        url.searchParams.set(param, currentMonthStart(timezone))
        return NextResponse.redirect(url, 307)
      }
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
}
