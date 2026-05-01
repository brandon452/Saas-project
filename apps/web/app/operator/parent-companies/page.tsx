"use client"

import { FormEvent, useEffect, useState } from "react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { apiRequest } from "@/lib/api"
import { useAuth } from "@/lib/hooks/useAuth"

interface ParentCompany {
  id: string
  name: string
  slug: string
  is_active: boolean
  created_at: string
}

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

export default function OperatorParentCompaniesPage() {
  const router = useRouter()
  const { user, isLoading } = useAuth()
  const [parentCompanies, setParentCompanies] = useState<ParentCompany[]>([])
  const [companyName, setCompanyName] = useState("")
  const [companySlug, setCompanySlug] = useState("")
  const [setPasswordUrl, setSetPasswordUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (isLoading) return
    if (!user) {
      router.replace("/login")
      return
    }
    if (!user.is_superuser) {
      router.replace("/")
    }
  }, [isLoading, router, user])

  useEffect(() => {
    if (!user?.is_superuser) return

    async function loadParentCompanies() {
      try {
        setParentCompanies(await apiRequest<ParentCompany[]>("operator/parent-companies/"))
      } catch {
        setError("Could not load parent companies.")
      }
    }

    loadParentCompanies()
  }, [user?.is_superuser])

  function handleCompanyNameChange(value: string) {
    setCompanyName(value)
    setCompanySlug((current) => current || slugify(value))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSetPasswordUrl(null)
    setSaving(true)

    const form = event.currentTarget
    const payload = {
      parent_company_name: companyName,
      parent_company_slug: companySlug,
      first_name: (form.elements.namedItem("first_name") as HTMLInputElement).value,
      last_name: (form.elements.namedItem("last_name") as HTMLInputElement).value,
      email: (form.elements.namedItem("email") as HTMLInputElement).value,
    }

    try {
      const created = await apiRequest<{ parent_company: ParentCompany; set_password_url: string }>("operator/parent-companies/", {
        method: "POST",
        body: JSON.stringify(payload),
      })
      setParentCompanies((current) => [...current, created.parent_company].sort((a, b) => a.name.localeCompare(b.name)))
      setSetPasswordUrl(created.set_password_url)
      setCompanyName("")
      setCompanySlug("")
      form.reset()
    } catch (err) {
      setError(getErrorMessage((err as { data?: unknown })?.data, "Could not create parent company."))
    } finally {
      setSaving(false)
    }
  }

  if (isLoading || !user?.is_superuser) {
    return null
  }

  return (
    <main className="min-h-screen bg-background p-6">
      <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[1fr_420px]">
        <section className="space-y-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Parent Companies</h1>
            <p className="mt-2 text-sm text-muted-foreground">Create and review top-level customer groups.</p>
          </div>
          {user.is_parent_member ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => router.push("/parent/organizations")}
            >
              Go to Parent Workspace
            </Button>
          ) : null}
          <div className="overflow-hidden rounded-lg border border-border bg-card">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/50 text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Slug</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {parentCompanies.map((company) => (
                  <tr key={company.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3 font-medium">{company.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{company.slug}</td>
                    <td className="px-4 py-3">{company.is_active ? "Active" : "Inactive"}</td>
                  </tr>
                ))}
                {parentCompanies.length === 0 ? (
                  <tr>
                    <td className="px-4 py-6 text-muted-foreground" colSpan={3}>No parent companies yet.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <h2 className="text-lg font-semibold">New Parent Company</h2>
          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="parent_company_name">Company Name</Label>
              <Input
                id="parent_company_name"
                value={companyName}
                onChange={(event) => handleCompanyNameChange(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="parent_company_slug">Company Slug</Label>
              <Input
                id="parent_company_slug"
                value={companySlug}
                onChange={(event) => setCompanySlug(slugify(event.target.value))}
                required
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="first_name">Admin First Name</Label>
                <Input id="first_name" name="first_name" required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="last_name">Admin Last Name</Label>
                <Input id="last_name" name="last_name" required />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Admin Email</Label>
              <Input id="email" name="email" type="email" required />
            </div>
            {error ? (
              <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </p>
            ) : null}
            {setPasswordUrl ? (
              <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                <p className="font-medium">Parent admin invite created.</p>
                <p className="mt-1 break-all">{setPasswordUrl}</p>
              </div>
            ) : null}
            <Button type="submit" disabled={saving} className="w-full">
              {saving ? "Creating..." : "Create Parent Company"}
            </Button>
          </form>
        </section>
      </div>
    </main>
  )
}
