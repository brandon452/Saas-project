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
import { useStockTakeMutations } from "@/lib/hooks/stock-takes/useStockTakeMutations"
import type { CycleItemClass } from "@/lib/types/stock-takes"

interface GenerateCycleCountDialogProps {
  orgId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  branches: Array<{ id: string; name: string }>
}

const cycleClasses: Array<{ value: CycleItemClass; label: string }> = [
  { value: "A", label: "Class A (7 days)" },
  { value: "B", label: "Class B (30 days)" },
  { value: "C", label: "Class C (90 days)" },
]

export function GenerateCycleCountDialog({
  orgId,
  open,
  onOpenChange,
  branches,
}: GenerateCycleCountDialogProps) {
  const router = useRouter()
  const { generateCycleCount } = useStockTakeMutations(orgId)
  const [branchId, setBranchId] = useState("")
  const [cycleItemClass, setCycleItemClass] = useState<CycleItemClass>("A")
  const [scheduledFor, setScheduledFor] = useState("")
  const [branchError, setBranchError] = useState("")
  const [formError, setFormError] = useState("")

  const sortedBranches = useMemo(
    () => [...branches].sort((a, b) => a.name.localeCompare(b.name)),
    [branches],
  )

  useEffect(() => {
    if (!open) {
      setBranchId("")
      setCycleItemClass("A")
      setScheduledFor("")
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
      const generated = await generateCycleCount.mutateAsync({
        branch_id: branchId,
        cycle_item_class: cycleItemClass,
        scheduled_for: scheduledFor || undefined,
      })
      onOpenChange(false)
      router.push(`/orgs/${orgId}/stock-takes/${generated.id}`)
    } catch (error) {
      const message = error instanceof Error ? error.message : ""
      if (message.includes("403")) {
        setFormError("You do not have permission to generate cycle counts.")
      } else if (message.includes("400")) {
        setFormError("Could not generate cycle count.")
      } else {
        setFormError(message || "Could not generate cycle count.")
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Generate Cycle Count</DialogTitle>
          <DialogDescription>
            Create a cycle stock take for a branch and item class.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="cycle-count-branch">Branch</Label>
          <select
            id="cycle-count-branch"
            value={branchId}
            onChange={(event) => {
              setBranchId(event.target.value)
              setBranchError("")
            }}
            disabled={generateCycleCount.isPending}
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
          <Label htmlFor="cycle-count-class">Cycle Class</Label>
          <select
            id="cycle-count-class"
            value={cycleItemClass}
            onChange={(event) => setCycleItemClass(event.target.value as CycleItemClass)}
            disabled={generateCycleCount.isPending}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            {cycleClasses.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="cycle-count-date">Scheduled For (Optional)</Label>
          <input
            id="cycle-count-date"
            type="date"
            value={scheduledFor}
            onChange={(event) => setScheduledFor(event.target.value)}
            disabled={generateCycleCount.isPending}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          />
        </div>

        {formError ? <p className="text-sm text-red-600">{formError}</p> : null}

        <DialogFooter>
          <DialogClose disabled={generateCycleCount.isPending}>Cancel</DialogClose>
          <Button onClick={handleSubmit} disabled={generateCycleCount.isPending}>
            {generateCycleCount.isPending ? "Generating..." : "Generate Cycle Count"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
