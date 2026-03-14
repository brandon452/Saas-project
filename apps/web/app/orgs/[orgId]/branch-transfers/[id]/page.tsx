"use client"

import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { useState } from "react"

import { BranchTransferDirectionBadge } from "@/components/branch-transfers/BranchTransferDirectionBadge"
import { BranchTransferStatusBadge } from "@/components/branch-transfers/BranchTransferStatusBadge"
import { ReceiveTransferForm } from "@/components/branch-transfers/ReceiveTransferForm"
import { TransferLineTable } from "@/components/branch-transfers/TransferLineTable"
import { ConfirmDialog } from "@/components/shared/ConfirmDialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useApproveTransfer,
  useCancelTransfer,
  useDispatchTransfer,
  useReceiveTransfer,
} from "@/lib/hooks/branch-transfers/useBranchTransferMutations"
import { useBranchTransfer } from "@/lib/hooks/branch-transfers/useBranchTransfer"
import { useNetworkBranches } from "@/lib/hooks/branch-transfers/useNetworkBranches"
import { useAuth } from "@/lib/hooks/useAuth"
import { useOrg } from "@/lib/hooks/useOrg"
import type { ReceiveTransferPayload } from "@/lib/types/branch-transfers"

function formatMaybeDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "\u2014"
}

function truncateUuid(value: string | null | undefined) {
  if (!value) return "\u2014"
  return `${value.slice(0, 8)}...`
}

export default function BranchTransferDetailPage() {
  const params = useParams<{ orgId: string; id: string }>()
  const router = useRouter()
  const { user } = useAuth()
  const { orgId, role } = useOrg()
  const transferId = params?.id ?? ""

  const transferQuery = useBranchTransfer(orgId, transferId)
  const networkBranchesQuery = useNetworkBranches(orgId)
  const approveTransfer = useApproveTransfer(orgId, transferId)
  const dispatchTransfer = useDispatchTransfer(orgId, transferId)
  const receiveTransfer = useReceiveTransfer(orgId, transferId)
  const cancelTransfer = useCancelTransfer(orgId, transferId)

  const [approveDialogOpen, setApproveDialogOpen] = useState(false)
  const [dispatchDialogOpen, setDispatchDialogOpen] = useState(false)
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
  const [receiveOpen, setReceiveOpen] = useState(false)
  const [actionError, setActionError] = useState("")

  const branchMap = new Map((networkBranchesQuery.data ?? []).map((branch) => [branch.id, branch]))
  const errorMessage = transferQuery.error instanceof Error ? transferQuery.error.message : ""

  if (transferQuery.isLoading) {
    return <DetailSkeleton />
  }

  if (errorMessage.includes("404")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Branch transfer not found</CardTitle>
        </CardHeader>
        <CardContent>
          <Link href={`/orgs/${orgId}/branch-transfers`} className="text-sm text-primary">
            Back to branch transfers
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (errorMessage.includes("403")) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Access denied</CardTitle>
        </CardHeader>
        <CardContent>
          <Link href={`/orgs/${orgId}/branch-transfers`} className="text-sm text-primary">
            Back to branch transfers
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (!transferQuery.data || transferQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Could not load branch transfer</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">Try loading the page again.</p>
          <Button onClick={() => void transferQuery.refetch()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  const transfer = transferQuery.data
  const isSender = transfer.organization === orgId
  const isReceiver = transfer.to_organization === orgId
  const isSameOrgTransfer = isSender && isReceiver
  const isParentUser =
    user?.parent_role === "PARENT_ADMIN" || user?.parent_role === "PARENT_VIEWER"
  const canSendActions = !isParentUser && (role === "OWNER" || role === "ADMIN") && isSender
  const canReceiveActions = !isParentUser && isReceiver
  const showSenderActions =
    canSendActions &&
    (transfer.status === "DRAFT" || transfer.status === "APPROVED")
  const showReceiverActions =
    canReceiveActions && transfer.status === "IN_TRANSIT" && (!isSameOrgTransfer || !showSenderActions)
  const actionPending =
    approveTransfer.isPending ||
    dispatchTransfer.isPending ||
    receiveTransfer.isPending ||
    cancelTransfer.isPending

  async function handleApprove() {
    try {
      setActionError("")
      await approveTransfer.mutateAsync()
      await transferQuery.refetch()
    } catch (error) {
      setActionError(error instanceof Error && error.message.includes("403") ? "You do not have permission to approve this transfer." : "Failed to approve the transfer.")
    }
  }

  async function handleDispatch() {
    try {
      setActionError("")
      await dispatchTransfer.mutateAsync()
      await transferQuery.refetch()
    } catch (error) {
      setActionError(error instanceof Error && error.message.includes("403") ? "You do not have permission to dispatch this transfer." : "Failed to dispatch the transfer.")
    }
  }

  async function handleCancel() {
    try {
      setActionError("")
      await cancelTransfer.mutateAsync()
      await transferQuery.refetch()
    } catch (error) {
      setActionError(error instanceof Error && error.message.includes("403") ? "You do not have permission to cancel this transfer." : "Failed to cancel the transfer.")
    }
  }

  async function handleReceive(payload: ReceiveTransferPayload) {
    try {
      setActionError("")
      await receiveTransfer.mutateAsync(payload)
      setReceiveOpen(false)
      await transferQuery.refetch()
    } catch (error) {
      setActionError(error instanceof Error && error.message.includes("403") ? "You do not have permission to receive this transfer." : "Failed to receive the transfer.")
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="space-y-2">
          <div className="text-sm text-muted-foreground">
            <Link href={`/orgs/${orgId}/branch-transfers`} className="hover:text-foreground">
              Branch Transfers
            </Link>{" "}
            / {truncateUuid(transfer.id)}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <BranchTransferStatusBadge status={transfer.status} />
            <BranchTransferDirectionBadge transfer={transfer} orgId={orgId} />
          </div>
        </div>
        <Button variant="ghost" onClick={() => router.push(`/orgs/${orgId}/branch-transfers`)}>
          Back
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Transfer details</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm text-muted-foreground md:grid-cols-2">
          <p>From Branch: {branchMap.get(transfer.from_branch)?.name ?? "\u2014"}</p>
          <p>To Branch: {branchMap.get(transfer.to_branch)?.name ?? "\u2014"}</p>
          <p>From Org: {branchMap.get(transfer.from_branch)?.org_name ?? "\u2014"}</p>
          <p>To Org: {branchMap.get(transfer.to_branch)?.org_name ?? "\u2014"}</p>
          <p>Created: {new Date(transfer.created_at).toLocaleString()}</p>
          <p>Dispatched: {formatMaybeDate(transfer.dispatched_at)}</p>
          <p>Received: {formatMaybeDate(transfer.received_at)}</p>
          <p>Notes: {transfer.notes.trim() || "\u2014"}</p>
          {transfer.status === "RECEIVED_COMPLETE" || transfer.status === "RECEIVED_WITH_VARIANCE" ? (
            <p className="md:col-span-2">
              Receive notes: {transfer.receive_notes.trim() || "\u2014"}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Lines</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <TransferLineTable transfer={transfer} />
          {showReceiverActions && receiveOpen ? (
            <ReceiveTransferForm
              transfer={transfer}
              onSubmit={(payload) => void handleReceive(payload)}
              onCancel={() => setReceiveOpen(false)}
              isPending={receiveTransfer.isPending}
            />
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Actions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {showSenderActions ? (
            <div className="flex flex-wrap gap-3">
              {transfer.status === "DRAFT" ? (
                <Button disabled={actionPending} onClick={() => setApproveDialogOpen(true)}>
                  Approve
                </Button>
              ) : null}
              {transfer.status === "APPROVED" ? (
                <Button disabled={actionPending} onClick={() => setDispatchDialogOpen(true)}>
                  Dispatch
                </Button>
              ) : null}
              {transfer.status === "DRAFT" || transfer.status === "APPROVED" ? (
                <Button variant="ghost" disabled={actionPending} onClick={() => setCancelDialogOpen(true)}>
                  Cancel
                </Button>
              ) : null}
            </div>
          ) : null}

          {showReceiverActions && !receiveOpen ? (
            <Button disabled={actionPending} onClick={() => setReceiveOpen(true)}>
              Receive
            </Button>
          ) : null}

          {!showSenderActions && !showReceiverActions ? (
            <p className="text-sm text-muted-foreground">No actions available for this transfer.</p>
          ) : null}

          {actionError ? <p className="text-sm text-red-600">{actionError}</p> : null}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={approveDialogOpen}
        onOpenChange={setApproveDialogOpen}
        title="Approve transfer"
        description="Are you sure you want to approve this transfer?"
        confirmLabel="Approve"
        onConfirm={() => {
          void handleApprove()
        }}
      />

      <ConfirmDialog
        open={dispatchDialogOpen}
        onOpenChange={setDispatchDialogOpen}
        title="Dispatch transfer"
        description="Are you sure you want to dispatch this transfer? This cannot be undone."
        confirmLabel="Dispatch"
        onConfirm={() => {
          void handleDispatch()
        }}
      />

      <ConfirmDialog
        open={cancelDialogOpen}
        onOpenChange={setCancelDialogOpen}
        title="Cancel transfer"
        description="Are you sure you want to cancel this transfer? This cannot be undone."
        confirmLabel="Cancel transfer"
        onConfirm={() => {
          void handleCancel()
        }}
        destructive
      />
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-52 w-full" />
      <Skeleton className="h-80 w-full" />
    </div>
  )
}
