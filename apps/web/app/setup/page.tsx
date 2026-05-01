"use client"

import { FormEvent, useEffect, useState } from "react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ""

function slugify(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
}

function getErrorMessage(data: unknown, fallback: string) {
  if (!data || typeof data !== "object") return fallback
  if ("detail" in data && typeof data.detail === "string") return data.detail
  const firstEntry = Object.values(data).find((value) => Array.isArray(value) || typeof value === "string")
  if (Array.isArray(firstEntry)) return firstEntry.join(" ")
  if (typeof firstEntry === "string") return firstEntry
  return fallback
}

export default function SetupPage() {
  const router = useRouter()
  const [setupRequired, setSetupRequired] = useState<boolean | null>(null)
  const [companyName, setCompanyName] = useState("")
  const [companySlug, setCompanySlug] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    async function loadStatus() {
      try {
        const res = await fetch(`${API_BASE}/api/setup/status/`, { credentials: "include" })
        const data = (await res.json()) as { setup_required?: boolean }
        setSetupRequired(data.setup_required === true)
      } catch {
        setError("Could not check setup status.")
      }
    }
    loadStatus()
  }, [])

  function handleCompanyNameChange(value: string) {
    setCompanyName(value)
    setCompanySlug((current) => current || slugify(value))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setLoading(true)

    const form = event.currentTarget
    const payload = {
      parent_company_name: companyName,
      parent_company_slug: companySlug,
      first_name: (form.elements.namedItem("first_name") as HTMLInputElement).value,
      last_name: (form.elements.namedItem("last_name") as HTMLInputElement).value,
      email: (form.elements.namedItem("email") as HTMLInputElement).value,
      password: (form.elements.namedItem("password") as HTMLInputElement).value,
    }

    try {
      const res = await fetch(`${API_BASE}/api/setup/first-run/`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        setError(getErrorMessage(data, "Setup failed."))
        return
      }
      router.replace("/parent/organizations")
    } catch {
      setError("Network error. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  if (setupRequired === null) {
    return <main className="min-h-dvh bg-background" />
  }

  if (!setupRequired) {
    return (
      <main className="flex min-h-dvh items-start justify-center bg-background px-4 py-10 sm:items-center sm:py-6">
        <section className="w-full max-w-md space-y-4 rounded-lg border border-border bg-card p-6 shadow-sm">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Setup Complete</h1>
            <p className="mt-2 text-sm text-muted-foreground">This instance already has a parent admin.</p>
          </div>
          <Button className="w-full" onClick={() => router.replace("/login")}>Go to Login</Button>
        </section>
      </main>
    )
  }

  return (
    <main className="flex min-h-dvh items-start justify-center bg-background px-4 py-10 sm:items-center">
      <section className="w-full max-w-2xl rounded-lg border border-border bg-card p-6 shadow-sm">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight">First-Run Setup</h1>
          <p className="mt-2 text-sm text-muted-foreground">Create the first parent company and parent admin.</p>
        </div>

        <form onSubmit={handleSubmit} className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="parent_company_name">Parent Company Name</Label>
            <Input
              id="parent_company_name"
              value={companyName}
              onChange={(event) => handleCompanyNameChange(event.target.value)}
              required
            />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="parent_company_slug">Parent Company Slug</Label>
            <Input
              id="parent_company_slug"
              value={companySlug}
              onChange={(event) => setCompanySlug(slugify(event.target.value))}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="first_name">Admin First Name</Label>
            <Input id="first_name" name="first_name" required />
          </div>
          <div className="space-y-2">
            <Label htmlFor="last_name">Admin Last Name</Label>
            <Input id="last_name" name="last_name" required />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="email">Admin Email</Label>
            <Input id="email" name="email" type="email" autoComplete="username" required />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="password">Admin Password</Label>
            <Input id="password" name="password" type="password" autoComplete="new-password" required />
          </div>
          {error ? (
            <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 sm:col-span-2">
              {error}
            </p>
          ) : null}
          <Button type="submit" disabled={loading} className="sm:col-span-2">
            {loading ? "Creating Setup..." : "Create Parent Admin"}
          </Button>
        </form>
      </section>
    </main>
  )
}
