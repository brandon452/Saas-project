"use client"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useParentMembers } from "@/lib/hooks/parent/useParentMembers"
import { useAuth } from "@/lib/hooks/useAuth"
import type { ParentMember } from "@/lib/types/parent"

export default function ParentUsersPage() {
  const { user } = useAuth()
  const membersQuery = useParentMembers()
  const members = membersQuery.data ?? []
  const activeCount = members.filter((member) => member.is_active).length

  if (membersQuery.isLoading) {
    return <ParentUsersSkeleton />
  }

  if (membersQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load parent users</CardTitle>
          <CardDescription>Refresh the page or try again in a moment.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => void membersQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Parent Users</h1>
        <p className="text-sm text-muted-foreground">
          Review users who can manage this parent company and its organizations.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <MetricCard label="Total Users" value={members.length} />
        <MetricCard label="Active Users" value={activeCount} />
        <MetricCard label="Your Role" value={user?.parent_role?.replace("_", " ") ?? "Parent User"} />
      </div>

      <Card>
        <CardContent className="p-0">
          {members.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">No parent users found.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((member) => (
                  <ParentUserRow key={member.id} member={member} />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Card>
      <CardHeader className="p-4">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="truncate text-xl">{value}</CardTitle>
      </CardHeader>
    </Card>
  )
}

function ParentUserRow({ member }: { member: ParentMember }) {
  const label = member.user.email || member.user.username

  return (
    <TableRow>
      <TableCell>
        <div className="flex min-w-0 flex-col">
          <span className="truncate font-medium">{label}</span>
          <span className="truncate text-xs text-muted-foreground">{member.user.username}</span>
        </div>
      </TableCell>
      <TableCell>
        <Badge variant={member.role === "PARENT_ADMIN" ? "default" : "secondary"}>
          {member.role.replace("_", " ")}
        </Badge>
      </TableCell>
      <TableCell>
        <Badge variant={member.is_active ? "default" : "outline"}>
          {member.is_active ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell>{new Date(member.created_at).toLocaleDateString()}</TableCell>
    </TableRow>
  )
}

function ParentUsersSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-48" />
      <div className="grid gap-4 sm:grid-cols-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
      <Skeleton className="h-80 w-full" />
    </div>
  )
}
