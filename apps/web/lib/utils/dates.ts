export function currentMonthStart(timezone?: string): string {
  const now = new Date()

  if (timezone) {
    try {
      const parts = new Intl.DateTimeFormat("en-CA", {
        timeZone: timezone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).formatToParts(now)
      const year = parts.find((p) => p.type === "year")?.value ?? ""
      const month = parts.find((p) => p.type === "month")?.value ?? ""
      return `${year}-${month}-01`
    } catch {
      // Invalid timezone string (e.g. cookie tampering) — fall through to UTC
    }
  }

  return `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}-01`
}
