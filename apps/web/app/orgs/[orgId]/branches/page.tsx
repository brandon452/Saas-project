"use client"

import { useEffect, useMemo, useState } from "react"

import { BranchPanel } from "@/components/branches/BranchPanel"
import { CreateBranchDialog } from "@/components/branches/CreateBranchDialog"
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
import { useBranches } from "@/lib/hooks/branches/useBranches"
import { useAuth } from "@/lib/hooks/useAuth"
import { useOrg } from "@/lib/hooks/useOrg"
import type { Branch } from "@/lib/types/branches"

export default function BranchesPage() {
  const { isLoading: authLoading } = useAuth()
  const { orgId, role } = useOrg()
  const branchesQuery = useBranches(orgId)

  const [selectedBranch, setSelectedBranch] = useState<Branch | null>(null)
  const [createOpen, setCreateOpen] = useState(false)

  const canManage = role === "OWNER" || role === "ADMIN"
  const branches = useMemo(() => branchesQuery.data ?? [], [branchesQuery.data])
  const errorMessage =
    branchesQuery.error instanceof Error ? branchesQuery.error.message : ""

  useEffect(() => {
    if (!selectedBranch) return

    const reboundBranch =
      branches.find((branch) => branch.id === selectedBranch.id) ?? null

    if (reboundBranch) {
      if (reboundBranch !== selectedBranch) {
        setSelectedBranch(reboundBranch)
      }
      return
    }

    if (!branchesQuery.isFetching) {
      setSelectedBranch(null)
    }
  }, [branches, branchesQuery.isFetching, selectedBranch])

  if (authLoading || branchesQuery.isLoading) {
    return <BranchesPageSkeleton />
  }

  if (!canManage) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Permission denied</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            You do not have permission to view branches in this organisation.
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
            You do not have permission to view branches in this organisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (branchesQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load branches</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            There was a problem loading branches. Try again.
          </p>
          <Button onClick={() => void branchesQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Branches</h1>
          <p className="text-sm text-muted-foreground">
            Manage branch names and reporting codes for this organisation.
          </p>
        </div>
        {canManage ? (
          <Button onClick={() => setCreateOpen(true)}>Create Branch</Button>
        ) : null}
      </div>

      <Card>
        <CardContent className="p-0">
          {branches.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No branches found for this organisation
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Code</TableHead>
                  {canManage ? <TableHead>Actions</TableHead> : null}
                </TableRow>
              </TableHeader>
              <TableBody>
                {branches.map((branch) => (
                  <TableRow
                    key={branch.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setSelectedBranch(branch)}
                  >
                    <TableCell className="font-medium">
                      <button
                        type="button"
                        className="text-left hover:underline"
                        onClick={(event) => {
                          event.stopPropagation()
                          setSelectedBranch(branch)
                        }}
                      >
                        {branch.name}
                      </button>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-mono">
                        {branch.code}
                      </Badge>
                    </TableCell>
                    {canManage ? (
                      <TableCell>
                        <Button
                          variant="ghost"
                          onClick={(event) => {
                            event.stopPropagation()
                            setSelectedBranch(branch)
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

      {canManage ? (
        <CreateBranchDialog
          open={createOpen}
          onOpenChange={setCreateOpen}
          orgId={orgId}
        />
      ) : null}

      <BranchPanel
        branch={selectedBranch}
        canManage={canManage}
        orgId={orgId}
        onClose={() => setSelectedBranch(null)}
      />
    </div>
  )
}

function BranchesPageSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-32" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}
