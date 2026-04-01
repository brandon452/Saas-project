/**
 * Reads the csrftoken cookie set by Django after login.
 */
export function getCsrfHeader(): Record<string, string> {
  if (typeof document === "undefined") return {}

  const match = document.cookie
    .split(";")
    .map((c) => c.trim())
    .find((c) => c.startsWith("csrftoken="))

  if (!match) return {}

  return { "X-CSRFToken": match.slice("csrftoken=".length) }
}
