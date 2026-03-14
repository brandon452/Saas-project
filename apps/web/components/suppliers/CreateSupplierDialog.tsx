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
import { useSupplierMutations } from "@/lib/hooks/suppliers/useSupplierMutations"

interface CreateSupplierDialogProps {
  orgId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CreateSupplierDialog({
  orgId,
  open,
  onOpenChange,
}: CreateSupplierDialogProps) {
  const { createSupplier } = useSupplierMutations(orgId)
  const [name, setName] = useState("")
  const [error, setError] = useState("")

  async function handleSubmit() {
    const trimmedName = name.trim()

    if (!trimmedName) {
      setError("Supplier name is required.")
      return
    }

    try {
      setError("")
      await createSupplier.mutateAsync({ name: trimmedName })
      onOpenChange(false)
      setName("")
    } catch (err) {
      const message = err instanceof Error ? err.message : ""
      if (message.includes("403")) {
        setError("You do not have permission to create suppliers.")
      } else if (message.includes("400")) {
        setError("Supplier name is invalid or already exists.")
      } else {
        setError("Could not create supplier.")
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Supplier</DialogTitle>
          <DialogDescription>Create a supplier for this organisation.</DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="supplier-name">Supplier name</Label>
          <Input
            id="supplier-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={createSupplier.isPending}
          />
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
        </div>

        <DialogFooter>
          <DialogClose disabled={createSupplier.isPending}>Cancel</DialogClose>
          <Button onClick={handleSubmit} disabled={createSupplier.isPending}>
            {createSupplier.isPending ? "Creating..." : "Create Supplier"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
