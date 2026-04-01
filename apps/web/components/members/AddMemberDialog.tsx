"use client"

import { useEffect, useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
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
import { useCreateUser } from "@/lib/hooks/useCreateUser"
import { ApiError, getApiErrorMessage } from "@/lib/api"
import type { MemberRole, UserSearchResult } from "@/lib/types/members"

interface AddMemberDialogProps {
  orgId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  currentRole: "OWNER" | "PARENT_ADMIN"
}

type DialogMode = "search" | "create" | "share"

const ASSIGNABLE_ROLES: Record<"OWNER" | "PARENT_ADMIN", MemberRole[]> = {
  PARENT_ADMIN: ["OWNER", "ADMIN", "STAFF"],
  OWNER: ["ADMIN", "STAFF"],
}

function getDisplayName(user: UserSearchResult) {
  return `${user.first_name} ${user.last_name}`.trim() || "—"
}

function getAddMemberErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return "You do not have permission to add members."
    }

    if (error.status === 400) {
      return "Could not add this member. The user may already belong to this organisation or have a conflicting membership."
    }
  }

  return "Could not add member."
}

function getCreateUserErrorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 403) {
    return "You do not have permission to create accounts."
  }

  return getApiErrorMessage(error, "Could not create account. Check the details and try again.")
}

export function AddMemberDialog({ orgId, open, onOpenChange, currentRole }: AddMemberDialogProps) {
  const { addMember } = useMemberMutations(orgId)
  const createUser = useCreateUser(orgId)
  const branchesQuery = usePOBranches(orgId)

  // Search / add-existing state
  const [email, setEmail] = useState("")
  const [debouncedEmail, setDebouncedEmail] = useState("")
  const [selectedUser, setSelectedUser] = useState<UserSearchResult | null>(null)
  const [addRole, setAddRole] = useState<MemberRole>("ADMIN")
  const [addBranchId, setAddBranchId] = useState("")
  const [addError, setAddError] = useState("")

  // Create account state
  const [mode, setMode] = useState<DialogMode>("search")
  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  const [createRole, setCreateRole] = useState<MemberRole>("ADMIN")
  const [createBranchId, setCreateBranchId] = useState("")
  const [createError, setCreateError] = useState("")

  // Share link state
  const [shareUrl, setShareUrl] = useState("")
  const [copied, setCopied] = useState(false)

  const searchQuery = useUserSearch(orgId, debouncedEmail)
  const branches = branchesQuery.data ?? []
  const searchResults = useMemo(() => searchQuery.data ?? [], [searchQuery.data])

  const assignableRoles = ASSIGNABLE_ROLES[currentRole]

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
    setAddRole("ADMIN")
    setAddBranchId("")
    setAddError("")
    setMode("search")
    setFirstName("")
    setLastName("")
    setCreateRole("ADMIN")
    setCreateBranchId("")
    setCreateError("")
    setShareUrl("")
    setCopied(false)
  }

  useEffect(() => {
    if (!open) resetState()
  }, [open])

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) resetState()
    onOpenChange(nextOpen)
  }

  async function handleAddExisting() {
    if (!selectedUser) {
      setAddError("Select a user to add.")
      return
    }
    if (addRole === "STAFF" && !addBranchId) {
      setAddError("Select a branch for STAFF members.")
      return
    }
    try {
      setAddError("")
      await addMember.mutateAsync({
        user_id: selectedUser.id,
        role: addRole,
        assigned_branch: addRole === "STAFF" ? addBranchId : undefined,
      })
      resetState()
      onOpenChange(false)
    } catch (err) {
      setAddError(getAddMemberErrorMessage(err))
    }
  }

  async function handleCreateAccount() {
    if (!firstName.trim() || !lastName.trim()) {
      setCreateError("First name and last name are required.")
      return
    }
    if (createRole === "STAFF" && !createBranchId) {
      setCreateError("Select a branch for STAFF members.")
      return
    }
    try {
      setCreateError("")
      const result = await createUser.mutateAsync({
        email: debouncedEmail,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        role: createRole,
        assigned_branch: createRole === "STAFF" ? createBranchId : null,
      })
      setShareUrl(result.set_password_url)
      setMode("share")
    } catch (err) {
      setCreateError(getCreateUserErrorMessage(err))
    }
  }

  function handleCopyLink() {
    navigator.clipboard.writeText(shareUrl).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    })
  }

  const showNoResults =
    debouncedEmail.length >= 3 &&
    !searchQuery.isLoading &&
    !searchQuery.isFetching &&
    searchResults.length === 0

  const addConfirmDisabled =
    addMember.isPending || !selectedUser || (addRole === "STAFF" && !addBranchId)

  // ── Share mode ─────────────────────────────────────────────────────────────
  if (mode === "share") {
    return (
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Account Created</DialogTitle>
            <DialogDescription>
              Share this link with the user so they can set their password. The link expires in 7 days.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2.5">
              <span className="flex-1 truncate text-sm text-muted-foreground">{shareUrl}</span>
              <Button type="button" variant="ghost" onClick={handleCopyLink}>
                {copied ? "Copied!" : "Copy"}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Send this link via WhatsApp, Slack, or any other channel. It can only be used once.
            </p>
          </div>

          <DialogFooter>
            <Button onClick={() => { resetState(); onOpenChange(false) }}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    )
  }

  // ── Create mode ─────────────────────────────────────────────────────────────
  if (mode === "create") {
    return (
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Create Account</DialogTitle>
            <DialogDescription>
              No account exists for <strong>{debouncedEmail}</strong>. Fill in the details to create one.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="create-first-name">First name</Label>
                <Input
                  id="create-first-name"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="Jane"
                  disabled={createUser.isPending}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="create-last-name">Last name</Label>
                <Input
                  id="create-last-name"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Smith"
                  disabled={createUser.isPending}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="create-email">Email</Label>
              <Input id="create-email" value={debouncedEmail} disabled />
            </div>

            <div className="space-y-2">
              <Label htmlFor="create-role">Role</Label>
              <select
                id="create-role"
                value={createRole}
                onChange={(e) => {
                  const next = e.target.value as MemberRole
                  setCreateRole(next)
                  if (next !== "STAFF") setCreateBranchId("")
                }}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
                disabled={createUser.isPending}
              >
                {assignableRoles.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>

            {createRole === "STAFF" && (
              <div className="space-y-2">
                <Label htmlFor="create-branch">Assigned branch</Label>
                <select
                  id="create-branch"
                  value={createBranchId}
                  onChange={(e) => setCreateBranchId(e.target.value)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
                  disabled={createUser.isPending || branchesQuery.isLoading}
                >
                  <option value="">Select a branch</option>
                  {branches.map((branch) => (
                    <option key={branch.id} value={String(branch.id)}>
                      {branch.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {createError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {createError}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => { setMode("search"); setCreateError("") }}
              disabled={createUser.isPending}
            >
              Back
            </Button>
            <Button
              onClick={handleCreateAccount}
              disabled={createUser.isPending || !firstName.trim() || !lastName.trim() || (createRole === "STAFF" && !createBranchId)}
            >
              {createUser.isPending ? "Creating..." : "Create Account"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    )
  }

  // ── Search mode (default) ────────────────────────────────────────────────────
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
                setAddError("")
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
                <div className="flex items-center justify-between p-4">
                  <span className="text-sm text-muted-foreground">No user found with this email</span>
                  <Button
                    type="button"
                    onClick={() => {
                      setCreateRole(assignableRoles[0])
                      setMode("create")
                    }}
                  >
                    Create Account
                  </Button>
                </div>
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
                        setAddError("")
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
                  value={addRole}
                  onChange={(event) => {
                    const nextRole = event.target.value as MemberRole
                    setAddRole(nextRole)
                    if (nextRole !== "STAFF") setAddBranchId("")
                  }}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
                  disabled={addMember.isPending}
                >
                  <option value="OWNER">OWNER</option>
                  <option value="ADMIN">ADMIN</option>
                  <option value="STAFF">STAFF</option>
                </select>
              </div>

              {addRole === "STAFF" ? (
                <div className="space-y-2">
                  <Label htmlFor="member-add-branch">Assigned branch</Label>
                  <select
                    id="member-add-branch"
                    value={addBranchId}
                    onChange={(event) => setAddBranchId(event.target.value)}
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

          {addError ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {addError}
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)} disabled={addMember.isPending}>
            Cancel
          </Button>
          <Button onClick={handleAddExisting} disabled={addConfirmDisabled}>
            {addMember.isPending ? "Adding..." : "Add Member"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
