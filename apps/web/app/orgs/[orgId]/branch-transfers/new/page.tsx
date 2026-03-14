"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"

import {
  TransferLineAddForm,
  type TransferLineDraft,
} from "@/components/branch-transfers/TransferLineAddForm"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { useCreateTransfer } from "@/lib/hooks/branch-transfers/useBranchTransferMutations"
import { useNetworkBranches } from "@/lib/hooks/branch-transfers/useNetworkBranches"
import { useAuth } from "@/lib/hooks/useAuth"
import { useOrg } from "@/lib/hooks/useOrg"

export default function NewBranchTransferPage() {
  const router = useRouter()
  const { user } = useAuth()
  const { orgId, canAccess } = useOrg()
  const networkBranchesQuery = useNetworkBranches(orgId)
  const createTransfer = useCreateTransfer(orgId)

  const [fromBranch, setFromBranch] = useState("")
  const [toBranch, setToBranch] = useState("")
  const [notes, setNotes] = useState("")
  const [lines, setLines] = useState<TransferLineDraft[]>([])
  const [submitError, setSubmitError] = useState("")

  useEffect(() => {
    if (!orgId) return
    if (user?.parent_role === "PARENT_ADMIN" || user?.parent_role === "PARENT_VIEWER") {
      router.replace(`/orgs/${orgId}/branch-transfers/`)
      return
    }
    if (!canAccess(["OWNER", "ADMIN"])) {
      router.replace(`/orgs/${orgId}/branch-transfers/`)
    }
  }, [canAccess, orgId, router, user?.parent_role])

  const networkBranches = networkBranchesQuery.data ?? []
  const ownBranches = networkBranches.filter((branch) => branch.org_id === orgId)
  const ownOrgName = ownBranches[0]?.org_name ?? "Current Organisation"
  const toBranchOptions = networkBranches.filter((branch) => branch.id !== fromBranch)
  const toBranchGroups = useMemo(() => {
    const groups = new Map<string, typeof toBranchOptions>()
    for (const branch of toBranchOptions) {
      const current = groups.get(branch.org_name) ?? []
      current.push(branch)
      groups.set(branch.org_name, current)
    }
    return Array.from(groups.entries())
  }, [toBranchOptions])
  const hasInvalidLines = lines.some((line) => line.quantity_sent <= 0)
  const isPending = createTransfer.isPending

  async function handleSubmit() {
    setSubmitError("")

    if (!fromBranch) {
      setSubmitError("From branch is required.")
      return
    }
    if (!toBranch) {
      setSubmitError("To branch is required.")
      return
    }
    if (fromBranch === toBranch) {
      setSubmitError("From branch and to branch must be different.")
      return
    }
    if (lines.length === 0) {
      setSubmitError("Add at least one line before submitting.")
      return
    }
    if (hasInvalidLines) {
      setSubmitError("Fix the transfer line quantities before submitting.")
      return
    }

    try {
      await createTransfer.mutateAsync({
        from_branch: fromBranch,
        to_branch: toBranch,
        notes,
        lines: lines.map((line) => ({
          item: line.item,
          quantity_sent: line.quantity_sent,
        })),
      })
    } catch {
      setSubmitError("Failed to create the branch transfer.")
    }
  }

  if (user?.parent_role === "PARENT_ADMIN" || user?.parent_role === "PARENT_VIEWER") {
    return null
  }

  if (!canAccess(["OWNER", "ADMIN"])) {
    return null
  }

  if (networkBranchesQuery.isLoading) {
    return <CreateSkeleton />
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="text-sm text-muted-foreground">
          <Link href={`/orgs/${orgId}/branch-transfers`} className="hover:text-foreground">
            Branch Transfers
          </Link>{" "}
          / New Branch Transfer
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">New Branch Transfer</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Transfer details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="from_branch">From branch</Label>
              <select
                id="from_branch"
                value={fromBranch}
                onChange={(event) => {
                  setFromBranch(event.target.value)
                  if (event.target.value === toBranch) {
                    setToBranch("")
                  }
                }}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
                disabled={isPending}
              >
                <option value="">Select branch</option>
                <optgroup label={ownOrgName}>
                  {ownBranches.map((branch) => (
                    <option key={branch.id} value={branch.id}>
                      {branch.name}
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="to_branch">To branch</Label>
              <select
                id="to_branch"
                value={toBranch}
                onChange={(event) => setToBranch(event.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
                disabled={isPending}
              >
                <option value="">Select branch</option>
                {toBranchGroups.map(([orgName, branches]) => (
                  <optgroup key={orgName} label={orgName}>
                    {branches.map((branch) => (
                      <option key={branch.id} value={branch.id}>
                        {branch.name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea
              id="notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              disabled={isPending}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Lines</CardTitle>
        </CardHeader>
        <CardContent>
          <TransferLineAddForm orgId={orgId} lines={lines} onChange={setLines} disabled={isPending} />
        </CardContent>
      </Card>

      {submitError ? <p className="text-sm text-red-600">{submitError}</p> : null}

      <div className="flex items-center justify-end gap-3">
        <Link
          href={`/orgs/${orgId}/branch-transfers`}
          className="inline-flex h-10 items-center justify-center rounded-md px-4 text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          Cancel
        </Link>
        <Button
          onClick={() => void handleSubmit()}
          disabled={
            isPending ||
            !fromBranch ||
            !toBranch ||
            fromBranch === toBranch ||
            lines.length === 0 ||
            hasInvalidLines
          }
        >
          {isPending ? "Saving..." : "Create Branch Transfer"}
        </Button>
      </div>
    </div>
  )
}

function CreateSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-52 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
