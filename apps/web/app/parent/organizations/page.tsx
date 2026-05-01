"use client"

import { FormEvent, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowRight, Settings, Users } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { getApiErrorMessage } from "@/lib/api"
import {
  useCreateParentOrganization,
  useParentOrganizations,
} from "@/lib/hooks/parent/useParentOrganizations"
import { useAuth } from "@/lib/hooks/useAuth"
import type { ParentOrganization } from "@/lib/types/parent"

function slugify(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
}

export default function ParentOrganizationsPage() {
  const router = useRouter()
  const { user } = useAuth()
  const organizationsQuery = useParentOrganizations()
  const createOrganization = useCreateParentOrganization()
  const [name, setName] = useState("")
  const [slug, setSlug] = useState("")
  const [error, setError] = useState("")

  const isParentAdmin = user?.parent_role === "PARENT_ADMIN"
  const organizations = organizationsQuery.data ?? []

  function handleNameChange(value: string) {
    setName(value)
    setSlug((current) => current || slugify(value))
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")

    const trimmedName = name.trim()
    const trimmedSlug = slugify(slug)

    if (!trimmedName || !trimmedSlug) {
      setError("Organization name and slug are required.")
      return
    }

    try {
      await createOrganization.mutateAsync({
        name: trimmedName,
        slug: trimmedSlug,
        is_active: true,
      })
      setName("")
      setSlug("")
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not create organization."))
    }
  }

  if (organizationsQuery.isLoading) {
    return <OrganizationsSkeleton />
  }

  if (organizationsQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load organizations</CardTitle>
          <CardDescription>Refresh the page or try again in a moment.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => void organizationsQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Organizations</h1>
        <p className="text-sm text-muted-foreground">
          Review customer organizations and jump into their operational workspaces.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3 sm:gap-4">
        <MetricCard label="Organizations" value={organizations.length} />
        <MetricCard label="Parent Role" value={user?.parent_role?.replace("_", " ") ?? "Parent User"} />
        <MetricCard label="Parent Company" value={organizations[0]?.parent_company_name ?? "Default Parent Company"} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <Card>
          <CardContent className="p-0">
            {organizations.length === 0 ? (
              <div className="p-8 text-center text-sm text-muted-foreground">No organizations found.</div>
            ) : (
              <>
                <div className="divide-y divide-border sm:hidden">
                  {organizations.map((organization) => (
                    <OrganizationMobileCard
                      key={organization.id}
                      organization={organization}
                      onDashboard={() => router.push(`/orgs/${organization.id}/dashboard`)}
                      onSettings={() => router.push(`/orgs/${organization.id}/settings`)}
                      onUsers={() => router.push(`/orgs/${organization.id}/users`)}
                    />
                  ))}
                </div>
                <Table className="hidden sm:table">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Slug</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {organizations.map((organization) => (
                      <OrganizationRow
                        key={organization.id}
                        organization={organization}
                        onDashboard={() => router.push(`/orgs/${organization.id}/dashboard`)}
                        onSettings={() => router.push(`/orgs/${organization.id}/settings`)}
                        onUsers={() => router.push(`/orgs/${organization.id}/users`)}
                      />
                    ))}
                  </TableBody>
                </Table>
              </>
            )}
          </CardContent>
        </Card>

        {isParentAdmin ? (
          <Card>
            <CardHeader className="p-4 sm:p-6">
              <CardTitle>New Organization</CardTitle>
              <CardDescription>Create an organization under this parent company.</CardDescription>
            </CardHeader>
            <CardContent className="p-4 pt-0 sm:p-6 sm:pt-0">
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="organization-name">Name</Label>
                  <Input
                    id="organization-name"
                    value={name}
                    onChange={(event) => handleNameChange(event.target.value)}
                    disabled={createOrganization.isPending}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="organization-slug">Slug</Label>
                  <Input
                    id="organization-slug"
                    value={slug}
                    onChange={(event) => setSlug(slugify(event.target.value))}
                    disabled={createOrganization.isPending}
                  />
                </div>
                {error ? (
                  <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                    {error}
                  </p>
                ) : null}
                <Button type="submit" disabled={createOrganization.isPending} className="w-full">
                  {createOrganization.isPending ? "Creating..." : "Create Organization"}
                </Button>
              </form>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Card>
      <CardHeader className="p-4">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="break-words text-lg sm:truncate sm:text-xl">{value}</CardTitle>
      </CardHeader>
    </Card>
  )
}

function OrganizationMobileCard({
  organization,
  onDashboard,
  onSettings,
  onUsers,
}: {
  organization: ParentOrganization
  onDashboard: () => void
  onSettings: () => void
  onUsers: () => void
}) {
  return (
    <div className="space-y-4 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="break-words text-sm font-semibold">{organization.name}</h2>
          <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{organization.slug}</p>
        </div>
        <Badge variant="default">Active</Badge>
      </div>
      <div className="grid grid-cols-[1fr_auto_auto] gap-2">
        <Button variant="outline" size="sm" onClick={onDashboard} className="justify-center">
          Open
          <ArrowRight className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="sm" onClick={onUsers} aria-label={`Open users for ${organization.name}`}>
          <Users className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="sm" onClick={onSettings} aria-label={`Open settings for ${organization.name}`}>
          <Settings className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

function OrganizationRow({
  organization,
  onDashboard,
  onSettings,
  onUsers,
}: {
  organization: ParentOrganization
  onDashboard: () => void
  onSettings: () => void
  onUsers: () => void
}) {
  return (
    <TableRow>
      <TableCell className="font-medium">{organization.name}</TableCell>
      <TableCell className="font-mono text-muted-foreground">{organization.slug}</TableCell>
      <TableCell>
        <Badge variant="default">Active</Badge>
      </TableCell>
      <TableCell>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onUsers} aria-label={`Open users for ${organization.name}`}>
            <Users className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={onSettings} aria-label={`Open settings for ${organization.name}`}>
            <Settings className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={onDashboard}>
            Open
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}

function OrganizationsSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-56" />
      <div className="grid gap-4 sm:grid-cols-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
