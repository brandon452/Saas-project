"use client"

import { useEffect, useMemo, useState } from "react"

import { useQueryClient } from "@tanstack/react-query"

import { ConfirmDialog } from "@/components/shared/ConfirmDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { useMemberMutations } from "@/lib/hooks/members/useMemberMutations"
import { usePOBranches } from "@/lib/hooks/purchase-orders/usePOBranches"
import type { Member, MemberRole, UpdateMemberPayload } from "@/lib/types/members"

interface MemberPanelProps {
  member: Member | null
  isOwner: boolean
  currentUserId: string
  orgId: string
  onClose: () => void
}

function getFullName(member: Member | null) {
  if (!member) return ""

  const fullName = `${member.user.first_name} ${member.user.last_name}`.trim()
  return fullName || member.user.email
}

function getPanelErrorMessage(error: unknown, action: "save" | "reactivate" | "deactivate") {
  const message = error instanceof Error ? error.message : ""

  if (message.includes("403")) {
    if (action === "deactivate") {
      return "You do not have permission to deactivate this member."
    }
    return "You do not have permission to manage this member."
  }

  if (message.includes("400")) {
    if (action === "reactivate") {
      return "Could not reactivate this member. Check the current role and branch assignment."
    }
    if (action === "deactivate") {
      return "Could not deactivate this member."
    }
    return "Could not save member changes. Check the role and branch assignment."
  }

  if (action === "reactivate") {
    return "Could not reactivate this member."
  }

  if (action === "deactivate") {
    return "Could not deactivate this member."
  }

  return "Could not save member changes."
}

function getRoleBadgeVariant(role: MemberRole) {
  if (role === "OWNER") return "default"
  if (role === "ADMIN") return "secondary"
  return "outline"
}

export function MemberPanel({
  member,
  isOwner,
  currentUserId,
  orgId,
  onClose,
}: MemberPanelProps) {
  const queryClient = useQueryClient()
  const { updateMember, deactivateMember } = useMemberMutations(orgId)
  const branchesQuery = usePOBranches(orgId)
  const [draftRole, setDraftRole] = useState<MemberRole>("ADMIN")
  const [draftBranchId, setDraftBranchId] = useState("")
  const [error, setError] = useState("")
  const [confirmOpen, setConfirmOpen] = useState(false)

  useEffect(() => {
    setDraftRole(member?.role ?? "ADMIN")
    setDraftBranchId(member?.assigned_branch?.id ?? "")
    setError("")
  }, [member])

  const branches = branchesQuery.data ?? []
  const showBranchSelector = draftRole === "STAFF"
  const currentBranchId = member?.assigned_branch?.id ?? ""
  const hasRoleChanged = !!member && draftRole !== member.role
  const hasBranchChanged = !!member && showBranchSelector && draftBranchId !== currentBranchId
  const needsBranchClear = !!member && member.role === "STAFF" && draftRole !== "STAFF"
  const hasChanges = hasRoleChanged || hasBranchChanged || needsBranchClear
  const isPending =
    updateMember.isPending || deactivateMember.isPending || branchesQuery.isFetching

  const canSave = !!member && isOwner && hasChanges && (!showBranchSelector || !!draftBranchId) && !isPending
  const fullName = useMemo(() => getFullName(member), [member])

  async function refreshMembers() {
    await queryClient.refetchQueries({ queryKey: ["members", orgId] })
  }

  async function handleSave() {
    if (!member || !canSave) return

    const payload: UpdateMemberPayload = {}

    if (hasRoleChanged) {
      payload.role = draftRole
    }

    if (draftRole === "STAFF") {
      payload.assigned_branch = draftBranchId
    } else if (member.role === "STAFF") {
      payload.assigned_branch = null
    }

    try {
      setError("")
      await updateMember.mutateAsync({ id: member.id, payload })
      await refreshMembers()
    } catch (err) {
      setError(getPanelErrorMessage(err, "save"))
    }
  }

  async function handleReactivate() {
    if (!member) return

    try {
      setError("")
      await updateMember.mutateAsync({ id: member.id, payload: { is_active: true } })
      await refreshMembers()
    } catch (err) {
      setError(getPanelErrorMessage(err, "reactivate"))
    }
  }

  async function handleDeactivate() {
    if (!member) return

    try {
      setError("")
      await deactivateMember.mutateAsync(member.id)
      await refreshMembers()
      setConfirmOpen(false)
    } catch (err) {
      setError(getPanelErrorMessage(err, "deactivate"))
    }
  }

  function resetDrafts() {
    setDraftRole(member?.role ?? "ADMIN")
    setDraftBranchId(member?.assigned_branch?.id ?? "")
    setError("")
  }

  return (
    <>
      <Sheet
        open={!!member}
        onOpenChange={(open) => {
          if (!open) {
            onClose()
          }
        }}
      >
        <SheetContent side="right">
          {member ? (
            <div className="space-y-6">
              <SheetHeader>
                <SheetTitle>{fullName}</SheetTitle>
                <SheetDescription className="space-y-3">
                  <span className="block">{member.user.email}</span>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant={getRoleBadgeVariant(member.role)}>{member.role}</Badge>
                    <Badge variant={member.is_active ? "default" : "secondary"}>
                      {member.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                </SheetDescription>
              </SheetHeader>

              <div className="space-y-4 rounded-xl border border-border p-4">
                <div className="space-y-1">
                  <p className="text-sm font-medium">Assigned branch</p>
                  <p className="text-sm text-muted-foreground">
                    {member.assigned_branch?.name ?? "-"}
                  </p>
                </div>
              </div>

              {isOwner ? (
                <div className="space-y-4 rounded-xl border border-border p-4">
                  <div className="space-y-2">
                    <Label htmlFor="member-role">Role</Label>
                    <select
                      id="member-role"
                      value={draftRole}
                      onChange={(event) => {
                        const nextRole = event.target.value as MemberRole
                        setDraftRole(nextRole)
                        if (nextRole !== "STAFF") {
                          setDraftBranchId("")
                        }
                      }}
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
                      disabled={isPending}
                    >
                      <option value="OWNER">OWNER</option>
                      <option value="ADMIN">ADMIN</option>
                      <option value="STAFF">STAFF</option>
                    </select>
                  </div>

                  {showBranchSelector ? (
                    <div className="space-y-2">
                      <Label htmlFor="member-branch">Assigned branch</Label>
                      <select
                        id="member-branch"
                        value={draftBranchId}
                        onChange={(event) => setDraftBranchId(event.target.value)}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
                        disabled={isPending || branchesQuery.isLoading}
                      >
                        <option value="">Select a branch</option>
                        {branches.map((branch) => (
                          <option key={branch.id} value={String(branch.id)}>
                            {branch.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : null}

                  {error ? (
                    <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                      {error}
                    </div>
                  ) : null}

                  <div className="flex gap-3">
                    <Button onClick={handleSave} disabled={!canSave}>
                      {updateMember.isPending ? "Saving..." : "Save"}
                    </Button>
                    <Button variant="ghost" onClick={resetDrafts} disabled={isPending}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : error ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {error}
                </div>
              ) : null}

              {isOwner ? (
                <div className="flex flex-wrap gap-3">
                  {member.is_active && member.user.id !== currentUserId ? (
                    <Button
                      variant="ghost"
                      className="text-red-600 hover:text-red-700"
                      onClick={() => setConfirmOpen(true)}
                      disabled={isPending}
                    >
                      Deactivate
                    </Button>
                  ) : null}

                  {!member.is_active ? (
                    <Button onClick={() => void handleReactivate()} disabled={isPending}>
                      {updateMember.isPending ? "Reactivating..." : "Reactivate"}
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </SheetContent>
      </Sheet>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Deactivate Member"
        description="Deactivate this member? They will lose access to this organisation."
        confirmLabel="Deactivate"
        onConfirm={() => {
          void handleDeactivate()
        }}
        destructive
      />
    </>
  )
}
