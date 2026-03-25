"use client"

import { useEffect, useState } from "react"

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
import { useBranchMutations } from "@/lib/hooks/branches/useBranchMutations"

interface CreateBranchDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  orgId: string
}

function getCreateBranchErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : ""

  if (message.includes("403")) {
    return "You do not have permission to create branches."
  }

  if (message.includes("400")) {
    return "Branch name or code is invalid."
  }

  return "Could not create branch."
}

export function CreateBranchDialog({
  open,
  onOpenChange,
  orgId,
}: CreateBranchDialogProps) {
  const { createBranch } = useBranchMutations(orgId)
  const [name, setName] = useState("")
  const [code, setCode] = useState("")
  const [error, setError] = useState("")

  const trimmedName = name.trim()
  const trimmedCode = code.trim()
  const canSubmit =
    !createBranch.isPending && trimmedName.length > 0 && trimmedCode.length > 0

  function resetState() {
    setName("")
    setCode("")
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
    if (!canSubmit) {
      setError("Name and code are required.")
      return
    }

    try {
      setError("")
      await createBranch.mutateAsync({
        name: trimmedName,
        code: trimmedCode,
      })
      resetState()
      onOpenChange(false)
    } catch (err) {
      setError(getCreateBranchErrorMessage(err))
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Branch</DialogTitle>
          <DialogDescription>Create a branch for this organisation.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="branch-create-name">Name</Label>
            <Input
              id="branch-create-name"
              value={name}
              onChange={(event) => {
                setName(event.target.value)
                setError("")
              }}
              disabled={createBranch.isPending}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="branch-create-code">Code</Label>
            <Input
              id="branch-create-code"
              value={code}
              onChange={(event) => {
                setCode(event.target.value)
                setError("")
              }}
              placeholder="e.g. KL, BR001, WH-NORTH"
              disabled={createBranch.isPending}
            />
            <p className="text-sm text-muted-foreground">
              Short identifier used in reports and displays
            </p>
          </div>

          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <DialogClose disabled={createBranch.isPending}>Cancel</DialogClose>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {createBranch.isPending ? "Creating..." : "Create Branch"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
