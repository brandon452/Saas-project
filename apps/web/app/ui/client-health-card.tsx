"use client"

import { useState } from "react"

import { apiRequest } from "../../lib/api-client"

export function ClientHealthCard() {
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)

  async function loadHealth() {
    setLoading(true)
    try {
      const response = await apiRequest("/api/health/")
      const data = (await response.json()) as Record<string, unknown>
      setResult(data)
    } catch {
      setResult({ detail: "Health API unreachable" })
    } finally {
      setLoading(false)
    }
  }

  return (
    <section style={{ marginTop: "1.5rem" }}>
      <h2>Client Component Health</h2>
      <button onClick={loadHealth} disabled={loading}>
        {loading ? "Loading..." : "Load Health"}
      </button>
      {result !== null && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </section>
  )
}
