"use client"

import { useEffect, useMemo, useState } from "react"
import { useIsFetching } from "@tanstack/react-query"

import { ConfirmDialog } from "@/components/shared/ConfirmDialog"
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
import { useOrgItemMutations } from "@/lib/hooks/org-items/useOrgItemMutations"
import { useOrg } from "@/lib/hooks/useOrg"
import type { OrgItem } from "@/lib/types/org-items"

interface OrgItemPanelProps {
  item: OrgItem | null
  canEdit: boolean
  onClose: () => void
  onDeactivated: () => void
}

function getUpdateErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : ""

  if (message.includes("403")) {
    return "You do not have permission to update items."
  }

  if (message.includes("400")) {
    return "Could not save the item name override."
  }

  return "Could not save item changes."
}

function getStatusErrorMessage(error: unknown, isReactivation: boolean) {
  const message = error instanceof Error ? error.message : ""

  if (message.includes("403")) {
    return isReactivation
      ? "You do not have permission to reactivate items."
      : "You do not have permission to deactivate items."
  }

  return isReactivation ? "Could not reactivate item." : "Could not deactivate item."
}

function truncateUuid(value: string) {
  if (value.length <= 12) return value
  return `${value.slice(0, 8)}...${value.slice(-4)}`
}

export function OrgItemPanel({
  item,
  canEdit,
  onClose,
  onDeactivated,
}: OrgItemPanelProps) {
  const { orgId } = useOrg()
  const { activateItem, updateOrgItem, deactivateOrgItem } = useOrgItemMutations(orgId)
  const [nameOverride, setNameOverride] = useState("")
  const [error, setError] = useState("")
  const [confirmOpen, setConfirmOpen] = useState(false)

  const listIsFetching = useIsFetching({ queryKey: ["org-items", orgId] }) > 0

  useEffect(() => {
    setNameOverride(item?.name_override ?? "")
    setError("")
  }, [item?.id, item?.name_override])

  const trimmedDraft = nameOverride.trim()
  const originalOverride = item?.name_override ?? ""
  const hasChanges = trimmedDraft !== originalOverride
  const mutationPending =
    updateOrgItem.isPending || deactivateOrgItem.isPending || activateItem.isPending
  const controlsDisabled = mutationPending || listIsFetching
  const canSave =
    !!item &&
    canEdit &&
    item.is_active &&
    hasChanges &&
    !controlsDisabled

  const statusBadge = useMemo(() => {
    if (!item) return null

    return (
      <Badge variant={item.is_active ? "default" : "secondary"}>
        {item.is_active ? "Active" : "Inactive"}
      </Badge>
    )
  }, [item])

  async function handleSave() {
    if (!item || !canSave) return

    try {
      setError("")
      await updateOrgItem.mutateAsync({
        id: item.id,
        payload: { name: trimmedDraft },
      })
    } catch (err) {
      setError(getUpdateErrorMessage(err))
    }
  }

  async function handleReactivate() {
    if (!item) return

    try {
      setError("")
      await activateItem.mutateAsync({ master_item: item.master_item })
      onClose()
    } catch (err) {
      setError(getStatusErrorMessage(err, true))
    }
  }

  async function handleDeactivate() {
    if (!item) return

    try {
      setError("")
      await deactivateOrgItem.mutateAsync(item.id)
      setConfirmOpen(false)
      onDeactivated()
    } catch (err) {
      setError(getStatusErrorMessage(err, false))
    }
  }

  return (
    <>
      <Sheet open={!!item} onOpenChange={(open) => !open && onClose()}>
        <SheetContent side="right">
          {item ? (
            <div className="space-y-6">
              <SheetHeader>
                <SheetTitle>{item.name}</SheetTitle>
                <SheetDescription className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className="font-mono">
                      {item.sku}
                    </Badge>
                    {statusBadge}
                  </div>
                  <div className="space-y-1 text-sm text-muted-foreground">
                    <p>Master item: {truncateUuid(item.master_item)}</p>
                    <p>Created: {new Date(item.created_at).toLocaleDateString()}</p>
                  </div>
                </SheetDescription>
              </SheetHeader>

              {canEdit ? (
                <div className="space-y-4 rounded-xl border border-border p-4">
                  <div className="space-y-2">
                    <Label htmlFor="org-item-name-override">Name override</Label>
                    <Input
                      id="org-item-name-override"
                      value={nameOverride}
                      onChange={(event) => setNameOverride(event.target.value)}
                      placeholder="Use global catalog name"
                      disabled={controlsDisabled || !item.is_active}
                    />
                  </div>

                  <div className="flex gap-3">
                    <Button onClick={handleSave} disabled={!canSave}>
                      {updateOrgItem.isPending ? "Saving..." : "Save"}
                    </Button>
                    <Button
                      variant="ghost"
                      disabled={controlsDisabled || !item.is_active}
                      onClick={() => {
                        setNameOverride(item.name_override)
                        setError("")
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : null}

              {error ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {error}
                </div>
              ) : null}

              {canEdit ? (
                <div className="flex gap-3">
                  {item.is_active ? (
                    <Button
                      variant="ghost"
                      className="text-red-600 hover:text-red-700"
                      disabled={controlsDisabled}
                      onClick={() => setConfirmOpen(true)}
                    >
                      Deactivate
                    </Button>
                  ) : (
                    <Button disabled={controlsDisabled} onClick={() => void handleReactivate()}>
                      {activateItem.isPending ? "Reactivating..." : "Reactivate"}
                    </Button>
                  )}
                </div>
              ) : null}
            </div>
          ) : null}
        </SheetContent>
      </Sheet>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Deactivate Item"
        description="Deactivate this item? It will be hidden from branch catalogs and item search."
        confirmLabel="Deactivate"
        onConfirm={() => {
          void handleDeactivate()
        }}
        destructive
      />
    </>
  )
}
