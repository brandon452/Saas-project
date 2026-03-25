"use client"

import { useState } from "react"

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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useMasterItemMutations } from "@/lib/hooks/master-items/useMasterItemMutations"

interface CreateMasterItemDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

function getCreateErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : ""

  if (message.includes("403")) {
    return "You do not have permission to create master items."
  }

  if (message.includes("400")) {
    return "Name or SKU is invalid, or the SKU already exists."
  }

  return "Could not create master item."
}

export function CreateMasterItemDialog({
  open,
  onOpenChange,
}: CreateMasterItemDialogProps) {
  const { createMasterItem } = useMasterItemMutations()
  const [name, setName] = useState("")
  const [sku, setSku] = useState("")
  const [error, setError] = useState("")

  async function handleSubmit() {
    const trimmedName = name.trim()
    const trimmedSku = sku.trim()

    if (!trimmedName || !trimmedSku) {
      setError("Name and SKU are required.")
      return
    }

    try {
      setError("")
      await createMasterItem.mutateAsync({
        name: trimmedName,
        sku: trimmedSku,
      })
      setName("")
      setSku("")
      onOpenChange(false)
    } catch (err) {
      setError(getCreateErrorMessage(err))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Master Item</DialogTitle>
          <DialogDescription>Create a network-wide catalog item for organisations to activate.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="master-item-name">Name</Label>
            <Input
              id="master-item-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              disabled={createMasterItem.isPending}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="master-item-sku">SKU</Label>
            <Input
              id="master-item-sku"
              value={sku}
              onChange={(event) => setSku(event.target.value)}
              disabled={createMasterItem.isPending}
            />
          </div>

          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <DialogClose disabled={createMasterItem.isPending}>Cancel</DialogClose>
          <Button onClick={handleSubmit} disabled={createMasterItem.isPending}>
            {createMasterItem.isPending ? "Creating..." : "Create Master Item"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
