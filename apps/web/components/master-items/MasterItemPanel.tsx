"use client"

import { useEffect, useMemo, useState } from "react"

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
import { useMasterItemDetail } from "@/lib/hooks/master-items/useMasterItemDetail"
import { useMasterItemMutations } from "@/lib/hooks/master-items/useMasterItemMutations"

interface MasterItemPanelProps {
  selectedId: string | null
  isParentAdmin: boolean
  onClose: () => void
  onDeactivated: () => void
}

function getUpdateErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : ""

  if (message.includes("403")) {
    return "You do not have permission to update catalog items."
  }

  if (message.includes("400")) {
    return "Name or SKU is invalid, or the SKU already exists."
  }

  return "Could not save catalog item changes."
}

function getStatusErrorMessage(error: unknown, isReactivation: boolean) {
  const message = error instanceof Error ? error.message : ""

  if (message.includes("403")) {
    return isReactivation
      ? "You do not have permission to reactivate catalog items."
      : "You do not have permission to deactivate catalog items."
  }

  return isReactivation ? "Could not reactivate catalog item." : "Could not deactivate catalog item."
}

export function MasterItemPanel({
  selectedId,
  isParentAdmin,
  onClose,
  onDeactivated,
}: MasterItemPanelProps) {
  const detailQuery = useMasterItemDetail(selectedId)
  const { updateMasterItem, deactivateMasterItem } = useMasterItemMutations()
  const [name, setName] = useState("")
  const [sku, setSku] = useState("")
  const [error, setError] = useState("")
  const [confirmOpen, setConfirmOpen] = useState(false)

  const item = detailQuery.data ?? null

  useEffect(() => {
    setName(item?.name ?? "")
    setSku(item?.sku ?? "")
    setError("")
  }, [selectedId, item?.id, item?.name, item?.sku])

  const trimmedName = name.trim()
  const trimmedSku = sku.trim()
  const originalName = item?.name.trim() ?? ""
  const originalSku = item?.sku.trim() ?? ""

  const hasChanges = trimmedName !== originalName || trimmedSku !== originalSku
  const isBusy = updateMasterItem.isPending || deactivateMasterItem.isPending
  const canEdit = isParentAdmin && !!item
  const canSave = canEdit && trimmedName.length > 0 && trimmedSku.length > 0 && hasChanges && !isBusy

  const statusBadge = useMemo(() => {
    if (!item) return null

    return <Badge variant={item.is_active ? "default" : "secondary"}>{item.is_active ? "Active" : "Inactive"}</Badge>
  }, [item])

  async function handleSave() {
    if (!item || !canSave) return

    try {
      setError("")
      await updateMasterItem.mutateAsync({
        id: item.id,
        payload: {
          name: trimmedName,
          sku: trimmedSku,
        },
      })
      await detailQuery.refetch()
    } catch (err) {
      setError(getUpdateErrorMessage(err))
    }
  }

  async function handleReactivate() {
    if (!item) return

    try {
      setError("")
      await updateMasterItem.mutateAsync({
        id: item.id,
        payload: { is_active: true },
      })
      onDeactivated()
    } catch (err) {
      setError(getStatusErrorMessage(err, true))
    }
  }

  async function handleDeactivate() {
    if (!item) return

    try {
      setError("")
      await deactivateMasterItem.mutateAsync(item.id)
      onDeactivated()
    } catch (err) {
      setError(getStatusErrorMessage(err, false))
    }
  }

  return (
    <>
      <Sheet open={!!selectedId} onOpenChange={(open) => !open && onClose()}>
        <SheetContent side="right">
          {detailQuery.isLoading ? (
            <div className="space-y-4">
              <div className="h-7 w-40 animate-pulse rounded bg-muted" />
              <div className="h-5 w-24 animate-pulse rounded bg-muted" />
              <div className="h-24 w-full animate-pulse rounded bg-muted" />
            </div>
          ) : detailQuery.isError ? (
            <div className="space-y-4">
              <SheetHeader>
                <SheetTitle>Could not load catalog item</SheetTitle>
                <SheetDescription>There was a problem loading this item.</SheetDescription>
              </SheetHeader>
              <Button onClick={() => void detailQuery.refetch()}>Retry</Button>
            </div>
          ) : item ? (
            <div className="space-y-6">
              <SheetHeader>
                <SheetTitle>{item.name}</SheetTitle>
                <SheetDescription className="flex items-center gap-2">
                  <Badge variant="outline" className="font-mono">
                    {item.sku}
                  </Badge>
                  {statusBadge}
                </SheetDescription>
              </SheetHeader>

              <div className="space-y-4">
                <div className="space-y-2 text-sm text-muted-foreground">
                  <p>Created: {new Date(item.created_at).toLocaleDateString()}</p>
                </div>

                {canEdit ? (
                  <div className="space-y-4 rounded-xl border border-border p-4">
                    <div className="space-y-2">
                      <Label htmlFor="master-item-panel-name">Name</Label>
                      <Input
                        id="master-item-panel-name"
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                        disabled={isBusy}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="master-item-panel-sku">SKU</Label>
                      <Input
                        id="master-item-panel-sku"
                        value={sku}
                        onChange={(event) => setSku(event.target.value)}
                        disabled={isBusy}
                      />
                    </div>

                    <div className="flex gap-3">
                      <Button onClick={handleSave} disabled={!canSave}>
                        {updateMasterItem.isPending ? "Saving..." : "Save"}
                      </Button>
                      <Button
                        variant="outline"
                        disabled={isBusy}
                        onClick={() => {
                          setName(item.name)
                          setSku(item.sku)
                          setError("")
                        }}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : null}
              </div>

              {error ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {error}
                </div>
              ) : null}

              {canEdit ? (
                <div className="flex gap-3">
                  {item.is_active ? (
                    <Button
                      variant="destructive"
                      disabled={isBusy}
                      onClick={() => setConfirmOpen(true)}
                    >
                      Deactivate
                    </Button>
                  ) : (
                    <Button disabled={isBusy} onClick={() => void handleReactivate()}>
                      {updateMasterItem.isPending ? "Reactivating..." : "Reactivate"}
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
        title="Deactivate Catalog Item"
        description="Deactivate this catalog item? Organizations will no longer be able to activate it."
        confirmLabel="Deactivate"
        onConfirm={() => {
          void handleDeactivate()
        }}
        destructive
      />
    </>
  )
}
