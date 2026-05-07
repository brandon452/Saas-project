"use client"

import { useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useBranchItems } from "@/lib/hooks/branch-items/useBranchItems"
import { useStockTakeMutations } from "@/lib/hooks/stock-takes/useStockTakeMutations"

interface CycleDuePanelProps {
  orgId: string
  branches: Array<{ id: string; name: string }>
}

type CycleClass = "A" | "B" | "C"

const classes: CycleClass[] = ["A", "B", "C"]

function toDateValue(value: string | null): Date | null {
  if (!value) return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

export function CycleDuePanel({ orgId, branches }: CycleDuePanelProps) {
  const [branchId, setBranchId] = useState("")
  const [message, setMessage] = useState("")
  const { generateCycleCount } = useStockTakeMutations(orgId)
  const branchItemsQuery = useBranchItems(orgId, branchId)

  const today = useMemo(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), now.getDate())
  }, [])

  const dueSummary = useMemo(() => {
    const rows = branchItemsQuery.data?.results ?? []
    return classes.map((itemClass) => {
      const rowsForClass = rows.filter((row) => row.item_class === itemClass)
      const overdue = rowsForClass.filter((row) => {
        const due = toDateValue(row.next_cycle_count_date)
        return due !== null && due < today
      }).length
      const dueToday = rowsForClass.filter((row) => {
        const due = toDateValue(row.next_cycle_count_date)
        return due !== null && due.getTime() === today.getTime()
      }).length
      const dueUnset = rowsForClass.filter((row) => row.next_cycle_count_date === null).length
      const upcoming = rowsForClass.filter((row) => {
        const due = toDateValue(row.next_cycle_count_date)
        return due !== null && due > today
      }).length

      return {
        itemClass,
        total: rowsForClass.length,
        overdue,
        dueToday,
        dueUnset,
        dueNow: overdue + dueToday + dueUnset,
        upcoming,
      }
    })
  }, [branchItemsQuery.data?.results, today])

  async function handleGenerate(itemClass: CycleClass) {
    if (!branchId) {
      setMessage("Pick a branch first.")
      return
    }
    try {
      setMessage("")
      const generated = await generateCycleCount.mutateAsync({
        branch_id: branchId,
        cycle_item_class: itemClass,
      })
      if (generated.created) {
        setMessage(`Generated cycle count ${generated.id} for class ${itemClass}.`)
      } else {
        setMessage(`Reused existing draft cycle count ${generated.id} for class ${itemClass}.`)
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : ""
      setMessage(text || `Could not generate class ${itemClass} cycle count.`)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cycle Due</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Branch</label>
          <select
            value={branchId}
            onChange={(event) => setBranchId(event.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none"
          >
            <option value="">Select a branch</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </select>
        </div>

        {branchId ? (
          <div className="overflow-auto rounded-md border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="p-2 text-left">Class</th>
                  <th className="p-2 text-left">Total Items</th>
                  <th className="p-2 text-left">Due Now</th>
                  <th className="p-2 text-left">Upcoming</th>
                  <th className="p-2 text-left">Action</th>
                </tr>
              </thead>
              <tbody>
                {dueSummary.map((row) => (
                  <tr key={row.itemClass} className="border-t">
                    <td className="p-2">{row.itemClass}</td>
                    <td className="p-2">{row.total}</td>
                    <td className="p-2">{row.dueNow}</td>
                    <td className="p-2">{row.upcoming}</td>
                    <td className="p-2">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={generateCycleCount.isPending}
                        onClick={() => void handleGenerate(row.itemClass)}
                      >
                        Generate
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
      </CardContent>
    </Card>
  )
}
