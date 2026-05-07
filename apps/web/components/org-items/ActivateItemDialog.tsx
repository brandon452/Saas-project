"use client"

import { useEffect, useMemo, useState } from "react"

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
import { useAvailableMasterItems } from "@/lib/hooks/org-items/useAvailableMasterItems"
import { useOrgItemMutations } from "@/lib/hooks/org-items/useOrgItemMutations"

interface ActivateItemDialogProps {
  orgId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

function getActivateErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : ""

  if (message.includes("403")) {
    return "You do not have permission to activate items."
  }

  if (message.includes("400")) {
    return "Could not activate this item. Check the selection and try again."
  }

  return "Could not activate item."
}

export function ActivateItemDialog({
  orgId,
  open,
  onOpenChange,
}: ActivateItemDialogProps) {
  const { activateItem } = useOrgItemMutations(orgId)
  const availableItemsQuery = useAvailableMasterItems(orgId, open)
  const [search, setSearch] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [nameOverride, setNameOverride] = useState("")
  const [error, setError] = useState("")

  const availableItems = useMemo(() => availableItemsQuery.data ?? [], [availableItemsQuery.data])

  const filteredItems = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()
    const sortedItems = [...availableItems].sort((left, right) => left.name.localeCompare(right.name))

    if (!normalizedSearch) {
      return sortedItems
    }

    return sortedItems.filter((item) => {
      const name = item.name.toLowerCase()
      const sku = item.sku.toLowerCase()
      return name.includes(normalizedSearch) || sku.includes(normalizedSearch)
    })
  }, [availableItems, search])

  function resetState() {
    setSearch("")
    setSelectedId(null)
    setNameOverride("")
    setError("")
  }

  useEffect(() => {
    if (!open) {
      resetState()
    }
  }, [open])

  async function handleSubmit() {
    if (!selectedId) {
      setError("Please select an item to continue.")
      return
    }

    const trimmedOverride = nameOverride.trim()

    try {
      setError("")
      await activateItem.mutateAsync({
        master_item: selectedId,
        name: trimmedOverride || undefined,
      })
      resetState()
      onOpenChange(false)
    } catch (err) {
      setError(getActivateErrorMessage(err))
    }
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      resetState()
    }
    onOpenChange(nextOpen)
  }

  const selectedItem = availableItems.find((item) => item.id === selectedId) ?? null
  const showBaseEmptyState = !availableItemsQuery.isLoading && availableItems.length === 0
  const showFilteredEmptyState = !availableItemsQuery.isLoading && availableItems.length > 0 && filteredItems.length === 0

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Add to Catalog</DialogTitle>
          <DialogDescription>
            Select an item from the catalog to add to this organization&apos;s inventory.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="activate-item-search">Search items</Label>
            <Input
              id="activate-item-search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Filter by name or SKU"
              disabled={activateItem.isPending}
            />
          </div>

          <div className="space-y-2">
            <Label>Available items</Label>
            <div className="max-h-72 space-y-2 overflow-y-auto rounded-xl border border-border p-2">
              {availableItemsQuery.isLoading ? (
                <div className="p-4 text-sm text-muted-foreground">Loading available items...</div>
              ) : showBaseEmptyState ? (
                <div className="p-4 text-sm text-muted-foreground">
                  All catalog items have been added. To reactivate a deactivated item, find it in the Items list and use the Edit panel.
                </div>
              ) : showFilteredEmptyState ? (
                <div className="p-4 text-sm text-muted-foreground">No items match your search</div>
              ) : (
                filteredItems.map((item) => {
                  const isSelected = item.id === selectedId

                  return (
                    <button
                      key={item.id}
                      type="button"
                      className={[
                        "w-full rounded-lg border px-3 py-3 text-left transition-colors",
                        isSelected
                          ? "border-primary bg-primary/5"
                          : "border-border hover:bg-muted/50",
                      ].join(" ")}
                      onClick={() => setSelectedId(item.id)}
                      disabled={activateItem.isPending}
                    >
                      <div className="font-medium">{item.name}</div>
                      <div className="text-sm text-muted-foreground">{item.sku}</div>
                    </button>
                  )
                })
              )}
            </div>
          </div>

          {selectedItem ? (
            <div className="space-y-2">
              <Label htmlFor="activate-item-override">Custom name</Label>
              <Input
                id="activate-item-override"
                value={nameOverride}
                onChange={(event) => setNameOverride(event.target.value)}
                placeholder="Leave blank to use the default catalog name"
                disabled={activateItem.isPending}
              />
            </div>
          ) : null}

          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <DialogClose disabled={activateItem.isPending}>Cancel</DialogClose>
          <Button
            onClick={handleSubmit}
            disabled={activateItem.isPending || !selectedId}
          >
            {activateItem.isPending ? "Adding..." : "Add to Catalog"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
