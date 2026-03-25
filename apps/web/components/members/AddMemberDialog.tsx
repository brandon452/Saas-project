"use client"

import { useEffect, useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useMemberMutations } from "@/lib/hooks/members/useMemberMutations"
import { useUserSearch } from "@/lib/hooks/members/useUserSearch"
import { usePOBranches } from "@/lib/hooks/purchase-orders/usePOBranches"
import type { MemberRole, UserSearchResult } from "@/lib/types/members"

interface AddMemberDialogProps {
  orgId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

function getDisplayName(user: UserSearchResult) {
  const fullName = `${user.first_name} ${user.last_name}`.trim()
  return fullName || user.email
}

function getAddMemberErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : ""

  if (message.includes("403")) {
    return "You do not have permission to add members."
  }

  if (message.includes("400")) {
    return "Could not add this member. The user may already belong to this organisation or have a conflicting membership."
  }

  return "Could not add member."
}

export function AddMemberDialog({ orgId, open, onOpenChange }: AddMemberDialogProps) {
  const { addMember } = useMemberMutations(orgId)
  const branchesQuery = usePOBranches(orgId)
  const [email, setEmail] = useState("")
  const [debouncedEmail, setDebouncedEmail] = useState("")
  const [selectedUser, setSelectedUser] = useState<UserSearchResult | null>(null)
  const [role, setRole] = useState<MemberRole>("ADMIN")
  const [branchId, setBranchId] = useState("")
  const [error, setError] = useState("")

  const searchQuery = useUserSearch(orgId, debouncedEmail)
  const branches = branchesQuery.data ?? []
  const searchResults = useMemo(() => searchQuery.data ?? [], [searchQuery.data])
  const showBranchSelector = role === "STAFF"

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedEmail(email.trim())
    }, 300)

    return () => window.clearTimeout(timer)
  }, [email])

  useEffect(() => {
    setSelectedUser((current) => {
      if (!current) return null
      return searchResults.find((result) => result.id === current.id) ?? current
    })
  }, [searchResults])

  function resetState() {
    setEmail("")
    setDebouncedEmail("")
    setSelectedUser(null)
    setRole("ADMIN")
    setBranchId("")
    setError("")
  }

  useEffect(() => {
    if (!open) {
      resetState()
    }
  }, [open])

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      resetState()
    }
    onOpenChange(nextOpen)
  }

  async function handleSubmit() {
    if (!selectedUser) {
      setError("Select a user to add.")
      return
    }

    if (role === "STAFF" && !branchId) {
      setError("Select a branch for STAFF members.")
      return
    }

    try {
      setError("")
      await addMember.mutateAsync({
        user_id: selectedUser.id,
        role,
        assigned_branch: role === "STAFF" ? branchId : undefined,
      })
      resetState()
      onOpenChange(false)
    } catch (err) {
      setError(getAddMemberErrorMessage(err))
    }
  }

  const confirmDisabled =
    addMember.isPending || !selectedUser || (showBranchSelector && !branchId)

  const showNoResults =
    debouncedEmail.length >= 3 &&
    !searchQuery.isLoading &&
    !searchQuery.isFetching &&
    searchResults.length === 0

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Add Member</DialogTitle>
          <DialogDescription>
            Search for an existing user by email, then choose their role for this organisation.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="member-email-search">User email</Label>
            <Input
              id="member-email-search"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value)
                setError("")
              }}
              placeholder="Enter an email address"
              disabled={addMember.isPending}
            />
          </div>

          <div className="space-y-2">
            <Label>Search results</Label>
            <div className="max-h-64 space-y-2 overflow-y-auto rounded-xl border border-border p-2">
              {debouncedEmail.trim().length < 3 ? (
                <div className="p-4 text-sm text-muted-foreground">
                  Enter at least 3 characters to search by email.
                </div>
              ) : searchQuery.isLoading || searchQuery.isFetching ? (
                <div className="p-4 text-sm text-muted-foreground">Searching users...</div>
              ) : showNoResults ? (
                <div className="p-4 text-sm text-muted-foreground">No user found with this email</div>
              ) : (
                searchResults.map((result) => {
                  const isSelected = selectedUser?.id === result.id

                  return (
                    <button
                      key={result.id}
                      type="button"
                      className={[
                        "w-full rounded-lg border px-3 py-3 text-left transition-colors",
                        isSelected
                          ? "border-primary bg-primary/5"
                          : "border-border hover:bg-muted/50",
                      ].join(" ")}
                      onClick={() => {
                        setSelectedUser(result)
                        setError("")
                      }}
                      disabled={addMember.isPending}
                    >
                      <div className="font-medium">{getDisplayName(result)}</div>
                      <div className="text-sm text-muted-foreground">{result.email}</div>
                    </button>
                  )
                })
              )}
            </div>
          </div>

          {selectedUser ? (
            <div className="space-y-4 rounded-xl border border-border p-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">Selected user</p>
                <p className="text-sm text-muted-foreground">{getDisplayName(selectedUser)}</p>
                <p className="text-sm text-muted-foreground">{selectedUser.email}</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="member-add-role">Role</Label>
                <select
                  id="member-add-role"
                  value={role}
                  onChange={(event) => {
                    const nextRole = event.target.value as MemberRole
                    setRole(nextRole)
                    if (nextRole !== "STAFF") {
                      setBranchId("")
                    }
                  }}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
                  disabled={addMember.isPending}
                >
                  <option value="OWNER">OWNER</option>
                  <option value="ADMIN">ADMIN</option>
                  <option value="STAFF">STAFF</option>
                </select>
              </div>

              {showBranchSelector ? (
                <div className="space-y-2">
                  <Label htmlFor="member-add-branch">Assigned branch</Label>
                  <select
                    id="member-add-branch"
                    value={branchId}
                    onChange={(event) => setBranchId(event.target.value)}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
                    disabled={addMember.isPending || branchesQuery.isLoading}
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
            </div>
          ) : null}

          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <DialogClose disabled={addMember.isPending}>Cancel</DialogClose>
          <Button onClick={handleSubmit} disabled={confirmDisabled}>
            {addMember.isPending ? "Adding..." : "Add Member"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
