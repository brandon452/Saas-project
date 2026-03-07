import { headers } from "next/headers"

import { apiRequest } from "../lib/api-client"
import { ClientHealthCard } from "./ui/client-health-card"

export default async function Page() {
  const host = headers().get("host") ?? "localhost:3000"

  let serverHealth: unknown = { detail: "Unavailable" }
  try {
    const response = await apiRequest("/api/health/")
    serverHealth = await response.json()
  } catch {
    serverHealth = { detail: "Health API unreachable" }
  }

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1>Inventory Dashboard</h1>
      <p>Host: {host}</p>
      <h2>Server Component Health</h2>
      <pre>{JSON.stringify(serverHealth, null, 2)}</pre>
      <ClientHealthCard />
    </main>
  )
}
