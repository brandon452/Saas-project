"use client"

import { useEffect, useState } from "react"

import { ConfirmDialog } from "@/components/shared/ConfirmDialog"
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
import { useSupplierMutations } from "@/lib/hooks/suppliers/useSupplierMutations"
import { useOrg } from "@/lib/hooks/useOrg"
import type { Supplier } from "@/lib/types/suppliers"
import { SupplierStatusBadge } from "./SupplierStatusBadge"

interface SupplierPanelProps {
  orgId: string
  supplier: Supplier | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSupplierChange: (supplier: Supplier) => void
}

export function SupplierPanel({
  orgId,
  supplier,
  open,
  onOpenChange,
  onSupplierChange,
}: SupplierPanelProps) {
  const { canAccess } = useOrg()
  const { updateSupplier, deactivateSupplier } = useSupplierMutations(orgId)
  const [name, setName] = useState("")
  const [error, setError] = useState("")
  const [confirmOpen, setConfirmOpen] = useState(false)

  useEffect(() => {
    setName(supplier?.name ?? "")
    setError("")
  }, [supplier])

  const canManage = canAccess(["OWNER", "ADMIN"])
  const isReadOnly = !supplier || !supplier.is_active || !canManage
  const trimmedName = name.trim()
  const trimmedOriginal = supplier?.name.trim() ?? ""
  const canSave =
    !!supplier &&
    supplier.is_active &&
    canManage &&
    trimmedName.length > 0 &&
    trimmedName !== trimmedOriginal &&
    !updateSupplier.isPending &&
    !deactivateSupplier.isPending

  async function handleSave() {
    if (!supplier || !canSave) return

    try {
      setError("")
      const updated = await updateSupplier.mutateAsync({ id: supplier.id, name: trimmedName })
      onSupplierChange(updated)
    } catch (err) {
      const message = err instanceof Error ? err.message : ""
      if (message.includes("403")) {
        setError("You do not have permission to update suppliers.")
      } else if (message.includes("400")) {
        setError("Supplier name is invalid or already exists.")
      } else {
        setError("Could not save supplier changes.")
      }
    }
  }

  async function handleDeactivate() {
    if (!supplier) return

    try {
      setError("")
      const updated = await deactivateSupplier.mutateAsync(supplier.id)
      onSupplierChange(updated)
    } catch (err) {
      const message = err instanceof Error ? err.message : ""
      if (message.includes("403")) {
        setError("You do not have permission to deactivate suppliers.")
      } else {
        setError("Could not deactivate supplier.")
      }
    }
  }

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right">
          {supplier ? (
            <div className="space-y-6">
              <SheetHeader>
                <SheetTitle>{supplier.name}</SheetTitle>
                <SheetDescription>
                  <SupplierStatusBadge isActive={supplier.is_active} />
                </SheetDescription>
              </SheetHeader>

              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="supplier-panel-name">Name</Label>
                  <Input
                    id="supplier-panel-name"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    readOnly={isReadOnly}
                    disabled={updateSupplier.isPending || deactivateSupplier.isPending}
                  />
                </div>

                <div className="space-y-2 text-sm text-muted-foreground">
                  <p>Created at: {new Date(supplier.created_at).toLocaleDateString()}</p>
                  <p>Updated at: {new Date(supplier.updated_at).toLocaleDateString()}</p>
                </div>
              </div>

              {error ? <p className="text-sm text-red-600">{error}</p> : null}

              {!isReadOnly ? (
                <div className="flex gap-3">
                  <Button onClick={handleSave} disabled={!canSave}>
                    Save
                  </Button>
                  <Button
                    variant="ghost"
                    className="text-red-600 hover:text-red-700"
                    disabled={updateSupplier.isPending || deactivateSupplier.isPending}
                    onClick={() => setConfirmOpen(true)}
                  >
                    Deactivate
                  </Button>
                </div>
              ) : null}
            </div>
          ) : null}
        </SheetContent>
      </Sheet>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Deactivate Supplier"
        description="This supplier will be marked inactive and will no longer appear in new purchase orders. This cannot be undone via the app."
        confirmLabel="Deactivate"
        onConfirm={() => {
          void handleDeactivate()
        }}
        destructive
      />
    </>
  )
}
