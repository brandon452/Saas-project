"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { AddMemberDialog } from "@/components/members/AddMemberDialog"
import { MemberPanel } from "@/components/members/MemberPanel"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useMembers } from "@/lib/hooks/members/useMembers"
import { useAuth } from "@/lib/hooks/useAuth"
import { useOrg } from "@/lib/hooks/useOrg"
import type { Member, MemberRole } from "@/lib/types/members"

function getDisplayName(member: Member) {
  return `${member.user.first_name} ${member.user.last_name}`.trim() || "—"
}

function getRoleBadgeVariant(role: MemberRole) {
  if (role === "OWNER") return "default"
  if (role === "ADMIN") return "secondary"
  return "outline"
}

export default function UsersPage() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { user, isLoading: authLoading } = useAuth()
  const { orgId, role, canAccess, isParentUser } = useOrg()

  const [selectedMember, setSelectedMember] = useState<Member | null>(null)
  const [addOpen, setAddOpen] = useState(false)

  const isOwner = role === "OWNER"
  const isParentAdmin = user?.parent_role === "PARENT_ADMIN"
  const canView = (!isParentUser && canAccess(["OWNER", "ADMIN"])) || isParentAdmin
  const canAddMembers = isOwner || isParentAdmin
  const isActiveParam = searchParams.get("is_active")
  const showInactive = isActiveParam === "false"

  const membersQuery = useMembers({
    orgId,
    is_active: showInactive ? "false" : undefined,
  })

  const members = useMemo(() => membersQuery.data ?? [], [membersQuery.data])

  useEffect(() => {
    if (!selectedMember) return

    const reboundMember = members.find((member) => member.id === selectedMember.id) ?? null

    if (reboundMember) {
      if (reboundMember !== selectedMember) {
        setSelectedMember(reboundMember)
      }
      return
    }

    if (!membersQuery.isFetching) {
      setSelectedMember(null)
    }
  }, [members, membersQuery.isFetching, selectedMember])

  const updateParams = useCallback(
    (next: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString())

      for (const [key, value] of Object.entries(next)) {
        if (!value) {
          params.delete(key)
        } else {
          params.set(key, value)
        }
      }

      const query = params.toString()
      router.replace(query ? `${pathname}?${query}` : pathname)
    },
    [pathname, router, searchParams],
  )

  const errorMessage = membersQuery.error instanceof Error ? membersQuery.error.message : ""

  if (authLoading || membersQuery.isLoading) {
    return <MembersPageSkeleton />
  }

  if (!canView) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view users in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (errorMessage.includes("403")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view users in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (membersQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load members</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            There was a problem loading members. Try again.
          </p>
          <Button onClick={() => void membersQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const emptyMessage = showInactive ? "No inactive members found" : "No members found"

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
          <p className="text-sm text-muted-foreground">
            View and manage organisation members and their access levels.
          </p>
        </div>
        {canAddMembers ? <Button onClick={() => setAddOpen(true)}>Add Member</Button> : null}
      </div>

      <div className="rounded-xl border border-border bg-card p-4">
        <label className="flex h-10 items-center gap-3 rounded-md border border-input bg-background px-3 text-sm">
          <input
            id="member-show-inactive"
            type="checkbox"
            checked={showInactive}
            onChange={(event) =>
              updateParams({
                is_active: event.target.checked ? "false" : null,
              })
            }
          />
          <span>Show inactive</span>
        </label>
      </div>

      <Card>
        <CardContent className="p-0">
          {members.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">{emptyMessage}</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Branch</TableHead>
                  <TableHead>Status</TableHead>
                  {isOwner ? <TableHead>Actions</TableHead> : null}
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((member) => (
                  <TableRow
                    key={member.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setSelectedMember(member)}
                  >
                    <TableCell className="font-medium">
                      <button
                        type="button"
                        className="text-left hover:underline"
                        onClick={(event) => {
                          event.stopPropagation()
                          setSelectedMember(member)
                        }}
                      >
                        {getDisplayName(member)}
                      </button>
                    </TableCell>
                    <TableCell>{member.user.email}</TableCell>
                    <TableCell>
                      <Badge variant={getRoleBadgeVariant(member.role)}>{member.role}</Badge>
                    </TableCell>
                    <TableCell>{member.assigned_branch?.name ?? "-"}</TableCell>
                    <TableCell>
                      <Badge variant={member.is_active ? "default" : "secondary"}>
                        {member.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    {isOwner ? (
                      <TableCell>
                        <Button
                          variant="ghost"
                          onClick={(event) => {
                            event.stopPropagation()
                            setSelectedMember(member)
                          }}
                        >
                          Edit
                        </Button>
                      </TableCell>
                    ) : null}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {canAddMembers ? (
        <AddMemberDialog
          orgId={orgId}
          open={addOpen}
          onOpenChange={setAddOpen}
          currentRole={isParentAdmin ? "PARENT_ADMIN" : "OWNER"}
        />
      ) : null}

      <MemberPanel
        member={selectedMember}
        isOwner={isOwner}
        currentUserId={user?.id ?? ""}
        orgId={orgId}
        onClose={() => setSelectedMember(null)}
      />
    </div>
  )
}

function MembersPageSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-32" />
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
