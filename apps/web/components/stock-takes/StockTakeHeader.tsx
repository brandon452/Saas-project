"use client"

import { useMemo, useState } from "react"

import { ConfirmDialog } from "@/components/shared/ConfirmDialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { useStockTakeMutations } from "@/lib/hooks/stock-takes/useStockTakeMutations"
import { usePOBranches } from "@/lib/hooks/purchase-orders/usePOBranches"
import { useOrg } from "@/lib/hooks/useOrg"
import type { StockTakeDetail } from "@/lib/types/stock-takes"
import { canEditNotes, formatDateTime, getStockTakeBranchLabel } from "@/lib/utils/stock-takes"
import { StockTakeStatusBadge } from "./StockTakeStatusBadge"

interface StockTakeHeaderProps {
  orgId: string
  stockTake: StockTakeDetail
  onChanged: () => Promise<void> | void
}

const ACTION_COPY = {
  start: "Start this stock take and create count lines for active branch items?",
  submit: "Submit this stock take for approval? Line editing will be locked.",
  approve: "Approve this stock take and post stock adjustment movements for all variances?",
  reopen: "Reopen this stock take for recount? Existing counted quantities will be preserved.",
  cancel: "Cancel this stock take? No adjustments will be posted.",
} as const

type StockTakeAction = keyof typeof ACTION_COPY

export function StockTakeHeader({ orgId, stockTake, onChanged }: StockTakeHeaderProps) {
  const { canAccess } = useOrg()
  const { updateStockTakeNotes, stockTakeAction } = useStockTakeMutations(orgId)
  const branchesQuery = usePOBranches(orgId)
  const [isEditingNotes, setIsEditingNotes] = useState(false)
  const [draftNotes, setDraftNotes] = useState(stockTake.notes ?? "")
  const [notesError, setNotesError] = useState("")
  const [actionError, setActionError] = useState("")
  const [pendingAction, setPendingAction] = useState<StockTakeAction | null>(null)
  const [openDialog, setOpenDialog] = useState<StockTakeAction | null>(null)

  const canManage = canAccess(["OWNER", "ADMIN"])
  const branchLabel = useMemo(
    () => getStockTakeBranchLabel(stockTake.branch, branchesQuery.data),
    [branchesQuery.data, stockTake.branch],
  )

  function beginEditNotes() {
    setDraftNotes(stockTake.notes ?? "")
    setNotesError("")
    setIsEditingNotes(true)
  }

  async function handleSaveNotes() {
    try {
      setNotesError("")
      await updateStockTakeNotes.mutateAsync({
        stockTakeId: stockTake.id,
        payload: { notes: draftNotes },
      })
      setIsEditingNotes(false)
      await onChanged()
    } catch (error) {
      const message = error instanceof Error ? error.message : ""
      if (message.includes("403")) {
        setNotesError("You do not have permission to update notes.")
      } else if (message.includes("400")) {
        setNotesError("Could not update notes.")
      } else {
        setNotesError(message || "Failed to update notes.")
      }
    }
  }

  async function handleAction(action: StockTakeAction) {
    try {
      setActionError("")
      setPendingAction(action)
      await stockTakeAction.mutateAsync({
        stockTakeId: stockTake.id,
        action,
      })
      setOpenDialog(null)
      await onChanged()
    } catch (error) {
      const message = error instanceof Error ? error.message : ""
      if (message.includes("403")) {
        setActionError("You do not have permission to perform this action.")
      } else if (message.includes("400")) {
        setActionError("Could not update stock take status.")
      } else {
        setActionError(message || "Failed to update stock take.")
      }
    } finally {
      setPendingAction(null)
    }
  }

  const actionButtons = {
    DRAFT: ["start", "cancel"],
    IN_PROGRESS: ["submit", "cancel"],
    PENDING_APPROVAL: ["reopen", "approve", "cancel"],
    COMPLETED: [],
    COMPLETED_WITH_VARIANCES: [],
    CANCELLED: [],
  } as const

  return (
    <>
      <Card>
        <CardHeader className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <CardTitle>{stockTake.id}</CardTitle>
              <StockTakeStatusBadge status={stockTake.status} />
            </div>
            <div className="grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
              <p>Branch: {branchLabel}</p>
              <p>Type: {stockTake.stock_take_type}</p>
              <p>Cycle class: {stockTake.cycle_item_class ?? "\u2014"}</p>
              <p>Scheduled for: {formatDateTime(stockTake.scheduled_for)}</p>
              <p>Created: {formatDateTime(stockTake.created_at)}</p>
              <p>Started: {formatDateTime(stockTake.started_at)}</p>
              <p>Snapshot taken: {formatDateTime(stockTake.snapshot_taken_at)}</p>
              <p>Submitted: {formatDateTime(stockTake.submitted_at)}</p>
              <p>Approved: {formatDateTime(stockTake.approved_at)}</p>
              <p>Cancelled: {formatDateTime(stockTake.cancelled_at)}</p>
              {stockTake.reopened_at ? (
                <>
                  <p>Reopened: {formatDateTime(stockTake.reopened_at)}</p>
                  <p>Reopened by: {stockTake.reopened_by?.username ?? "\u2014"}</p>
                </>
              ) : null}
            </div>
          </div>

          {canManage ? (
            <div className="flex flex-wrap gap-2">
              {actionButtons[stockTake.status].map((action) => (
                <Button
                  key={action}
                  variant={action === "cancel" ? "ghost" : "default"}
                  disabled={!!pendingAction}
                  onClick={() => setOpenDialog(action)}
                >
                  {action === "start"
                    ? "Start"
                    : action === "submit"
                      ? "Submit"
                      : action === "approve"
                        ? "Approve"
                        : action === "reopen"
                          ? "Reopen"
                          : "Cancel"}
                </Button>
              ))}
            </div>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-medium">Notes</h3>
              {canManage && canEditNotes(stockTake.status) && !isEditingNotes ? (
                <Button variant="ghost" className="px-2 py-1 text-xs" onClick={beginEditNotes}>
                  Edit Notes
                </Button>
              ) : null}
            </div>

            {isEditingNotes ? (
              <div className="space-y-3">
                <Textarea value={draftNotes} onChange={(event) => setDraftNotes(event.target.value)} />
                <div className="flex gap-2">
                  <Button disabled={updateStockTakeNotes.isPending} onClick={() => void handleSaveNotes()}>
                    {updateStockTakeNotes.isPending ? "Saving..." : "Save"}
                  </Button>
                  <Button
                    variant="ghost"
                    disabled={updateStockTakeNotes.isPending}
                    onClick={() => {
                      setDraftNotes(stockTake.notes ?? "")
                      setNotesError("")
                      setIsEditingNotes(false)
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">{stockTake.notes.trim() || "\u2014"}</p>
            )}

            {notesError ? <p className="text-sm text-red-600">{notesError}</p> : null}
          </div>

          {actionError ? <p className="text-sm text-red-600">{actionError}</p> : null}
        </CardContent>
      </Card>

      {(Object.keys(ACTION_COPY) as StockTakeAction[]).map((action) => (
        <ConfirmDialog
          key={action}
          open={openDialog === action}
          onOpenChange={(open) => setOpenDialog(open ? action : null)}
          title={
            action === "start"
              ? "Start stock take"
              : action === "submit"
                ? "Submit stock take"
                : action === "approve"
                  ? "Approve stock take"
                  : action === "reopen"
                    ? "Reopen stock take"
                    : "Cancel stock take"
          }
          description={ACTION_COPY[action]}
          confirmLabel={
            action === "start"
              ? "Start"
              : action === "submit"
                ? "Submit"
                : action === "approve"
                  ? "Approve"
                  : action === "reopen"
                    ? "Reopen"
                    : "Cancel"
          }
          onConfirm={() => {
            void handleAction(action)
          }}
          destructive={action === "cancel"}
        />
      ))}
    </>
  )
}
