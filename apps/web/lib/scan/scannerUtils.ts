const SEPARATOR_RE = /[\t\r\n\x1d]/g

export function normalizeToken(raw: string): string {
  return raw.replace(SEPARATOR_RE, "").trim().toUpperCase()
}

export function makeDebouncer(windowMs = 300) {
  let lastToken = ""
  let lastAt = 0

  return function isDuplicate(token: string): boolean {
    const now = Date.now()
    if (token === lastToken && now - lastAt < windowMs) {
      return true
    }
    lastToken = token
    lastAt = now
    return false
  }
}

export function isNonRetryableStatus(httpStatus: number): boolean {
  // 429 (rate limited) and 408 (request timeout) are transient — allow retry
  if (httpStatus === 429 || httpStatus === 408) return false
  return httpStatus >= 400 && httpStatus < 500
}

export function generateIdempotencyKey(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export function hashToken(token: string): string {
  let h = 0
  for (let i = 0; i < token.length; i++) {
    h = (Math.imul(31, h) + token.charCodeAt(i)) | 0
  }
  return (h >>> 0).toString(16).padStart(8, "0")
}
