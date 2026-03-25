"use client"

import { useEffect, useMemo, useState } from "react"

import { useQueryClient } from "@tanstack/react-query"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { useBranchMutations } from "@/lib/hooks/branches/useBranchMutations"
import type { Branch } from "@/lib/types/branches"

interface BranchPanelProps {
  branch: Branch | null
  canManage: boolean
  orgId: string
  onClose: () => void
}

function getUpdateBranchErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : ""

  if (message.includes("403")) {
    return "You do not have permission to update branches."
  }

  if (message.includes("400")) {
    return "Branch name or code is invalid."
  }

  return "Could not save branch changes."
}

export function BranchPanel({
  branch,
  canManage,
  orgId,
  onClose,
}: BranchPanelProps) {
  const queryClient = useQueryClient()
  const { updateBranch } = useBranchMutations(orgId)
  const [name, setName] = useState("")
  const [code, setCode] = useState("")
  const [error, setError] = useState("")

  useEffect(() => {
    setName(branch?.name ?? "")
    setCode(branch?.code ?? "")
    setError("")
  }, [branch?.id, branch?.name, branch?.code])

  const trimmedName = name.trim()
  const trimmedCode = code.trim()
  const originalName = branch?.name.trim() ?? ""
  const originalCode = branch?.code.trim() ?? ""
  const hasChanges =
    trimmedName !== originalName || trimmedCode !== originalCode
  const canSave =
    !!branch &&
    canManage &&
    trimmedName.length > 0 &&
    trimmedCode.length > 0 &&
    hasChanges &&
    !updateBranch.isPending

  const codeBadge = useMemo(() => {
    if (!branch) return null

    return (
      <Badge variant="outline" className="font-mono">
        {branch.code}
      </Badge>
    )
  }, [branch])

  async function handleSave() {
    if (!branch || !canSave) return

    try {
      setError("")
      await updateBranch.mutateAsync({
        id: branch.id,
        payload: {
          name: trimmedName,
          code: trimmedCode,
        },
      })
      await queryClient.refetchQueries({ queryKey: ["branches", orgId] })
    } catch (err) {
      setError(getUpdateBranchErrorMessage(err))
    }
  }

  function resetDrafts() {
    setName(branch?.name ?? "")
    setCode(branch?.code ?? "")
    setError("")
  }

  return (
    <Sheet open={!!branch} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right">
        {branch ? (
          <div className="space-y-6">
            <SheetHeader>
              <SheetTitle>{branch.name}</SheetTitle>
              <SheetDescription className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">{codeBadge}</div>
              </SheetDescription>
            </SheetHeader>

            <div className="space-y-4 rounded-xl border border-border p-4">
              <div className="space-y-2">
                <Label htmlFor="branch-panel-name">Name</Label>
                <Input
                  id="branch-panel-name"
                  value={name}
                  onChange={(event) => {
                    setName(event.target.value)
                    setError("")
                  }}
                  disabled={!canManage || updateBranch.isPending}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="branch-panel-code">Code</Label>
                <Input
                  id="branch-panel-code"
                  value={code}
                  onChange={(event) => {
                    setCode(event.target.value)
                    setError("")
                  }}
                  placeholder="e.g. KL, BR001, WH-NORTH"
                  disabled={!canManage || updateBranch.isPending}
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

              {canManage ? (
                <div className="flex gap-3">
                  <Button onClick={handleSave} disabled={!canSave}>
                    {updateBranch.isPending ? "Saving..." : "Save"}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={resetDrafts}
                    disabled={updateBranch.isPending}
                  >
                    Cancel
                  </Button>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
