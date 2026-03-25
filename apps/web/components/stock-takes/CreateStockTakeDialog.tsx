"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"

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
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useStockTakeMutations } from "@/lib/hooks/stock-takes/useStockTakeMutations"

interface CreateStockTakeDialogProps {
  orgId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  branches: Array<{ id: string; name: string }>
}

export function CreateStockTakeDialog({
  orgId,
  open,
  onOpenChange,
  branches,
}: CreateStockTakeDialogProps) {
  const router = useRouter()
  const { createStockTake } = useStockTakeMutations(orgId)
  const [branchId, setBranchId] = useState("")
  const [notes, setNotes] = useState("")
  const [branchError, setBranchError] = useState("")
  const [formError, setFormError] = useState("")

  const sortedBranches = useMemo(
    () => [...branches].sort((a, b) => a.name.localeCompare(b.name)),
    [branches],
  )

  useEffect(() => {
    if (!open) {
      setBranchId("")
      setNotes("")
      setBranchError("")
      setFormError("")
    }
  }, [open])

  async function handleSubmit() {
    if (!branchId) {
      setBranchError("Branch is required.")
      return
    }

    try {
      setBranchError("")
      setFormError("")
      const created = await createStockTake.mutateAsync({
        branch: branchId,
        notes: notes.trim() || undefined,
      })
      onOpenChange(false)
      router.push(`/orgs/${orgId}/stock-takes/${created.id}`)
    } catch (error) {
      const message = error instanceof Error ? error.message : ""
      if (message.includes("403")) {
        setFormError("You do not have permission to create stock takes.")
      } else if (message.includes("400")) {
        setFormError("Could not create stock take.")
      } else {
        setFormError(message || "Could not create stock take.")
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Stock Take</DialogTitle>
          <DialogDescription>Create a branch stock take for physical counting.</DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="stock-take-branch">Branch</Label>
          <select
            id="stock-take-branch"
            value={branchId}
            onChange={(event) => {
              setBranchId(event.target.value)
              setBranchError("")
            }}
            disabled={createStockTake.isPending}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            <option value="">Select a branch</option>
            {sortedBranches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </select>
          {branchError ? <p className="text-sm text-red-600">{branchError}</p> : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="stock-take-notes">Notes</Label>
          <Textarea
            id="stock-take-notes"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            disabled={createStockTake.isPending}
            placeholder="Optional notes"
          />
        </div>

        {formError ? <p className="text-sm text-red-600">{formError}</p> : null}

        <DialogFooter>
          <DialogClose disabled={createStockTake.isPending}>Cancel</DialogClose>
          <Button onClick={handleSubmit} disabled={createStockTake.isPending}>
            {createStockTake.isPending ? "Creating..." : "Create Stock Take"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
