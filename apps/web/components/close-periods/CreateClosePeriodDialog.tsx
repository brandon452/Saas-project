"use client"

import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useClosePeriodMutations } from "@/lib/hooks/close-periods/useClosePeriodMutations"
import { getApiErrorMessage } from "@/lib/api"
import type { ClosePeriod } from "@/lib/types/close-periods"

function toDateInputValue(date: Date) {
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return localDate.toISOString().slice(0, 10)
}

function getPreviousMonthDefaults() {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth() - 1, 1)
  const end = new Date(now.getFullYear(), now.getMonth(), 0)

  return {
    startDate: toDateInputValue(start),
    endDate: toDateInputValue(end),
  }
}

interface CreateClosePeriodDialogProps {
  orgId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: (period: ClosePeriod) => void
}

export function CreateClosePeriodDialog({
  orgId,
  open,
  onOpenChange,
  onCreated,
}: CreateClosePeriodDialogProps) {
  const { createPeriod, closePeriod } = useClosePeriodMutations(orgId)
  const today = toDateInputValue(new Date())
  const defaultDates = getPreviousMonthDefaults()

  const [startDate, setStartDate] = useState(defaultDates.startDate)
  const [endDate, setEndDate] = useState(defaultDates.endDate)
  const [notes, setNotes] = useState("")
  const [confirmed, setConfirmed] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!open) {
      const nextDefaults = getPreviousMonthDefaults()
      setStartDate(nextDefaults.startDate)
      setEndDate(nextDefaults.endDate)
      setNotes("")
      setConfirmed(false)
      setError("")
    }
  }, [open])

  const dateRangeInvalid = !!startDate && !!endDate && endDate < startDate
  const isPending = createPeriod.isPending || closePeriod.isPending
  const canSubmit = !!startDate && !!endDate && confirmed && !dateRangeInvalid && !isPending

  async function handleSubmit() {
    if (!canSubmit) return
    try {
      setError("")
      const result = await createPeriod.mutateAsync({
        start_date: startDate,
        end_date: endDate,
        notes,
      })
      const closed = await closePeriod.mutateAsync(result.id)
      onCreated(closed)
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not close period. Check the dates, cost data, and try again."))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Close Period</DialogTitle>
          <DialogDescription>
            Closing this period locks inventory movements within the selected date range and creates a valuation snapshot.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="cp-start-date">Start date</Label>
              <input
                id="cp-start-date"
                type="date"
                value={startDate}
                max={today}
                onChange={(e) => {
                  setStartDate(e.target.value)
                  setError("")
                }}
                disabled={isPending}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none disabled:opacity-50"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="cp-end-date">End date</Label>
              <input
                id="cp-end-date"
                type="date"
                value={endDate}
                max={today}
                onChange={(e) => {
                  setEndDate(e.target.value)
                  setError("")
                }}
                disabled={isPending}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none disabled:opacity-50"
              />
            </div>
          </div>

          {dateRangeInvalid ? (
            <p className="text-sm text-red-600">End date must be on or after start date.</p>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="cp-notes">Notes</Label>
            <Textarea
              id="cp-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes about this period"
              disabled={isPending}
              rows={3}
            />
          </div>

          <label className="flex items-start gap-3 rounded-lg border border-border bg-muted/30 p-3 text-sm">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
              disabled={isPending}
              className="mt-1"
            />
            <span>
              I understand this will lock inventory movements for the selected date range and create the period valuation snapshot.
            </span>
          </label>

          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {isPending ? "Closing..." : "Close Period"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
