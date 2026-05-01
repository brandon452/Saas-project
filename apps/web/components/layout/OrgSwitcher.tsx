"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { Building2, Check, ChevronsUpDown } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { useAccessibleOrgs } from "@/lib/hooks/useAccessibleOrgs"
import { useOrg } from "@/lib/hooks/useOrg"
import { cn } from "@/lib/utils"

export function OrgSwitcher() {
  const { orgId } = useOrg()
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")

  const { data: orgs = [] } = useAccessibleOrgs(true)
  const activeOrg = orgs.find((org) => org.id === orgId) ?? null
  const filteredOrgs = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return orgs
    return orgs.filter((org) => org.name.toLowerCase().includes(normalizedQuery))
  }, [orgs, query])

  function switchOrg(newOrgId: string) {
    handleOpenChange(false)
    router.push(`/orgs/${newOrgId}/dashboard`)
  }

  function handleOpenChange(nextOpen: boolean) {
    setOpen(nextOpen)
    if (!nextOpen) {
      setQuery("")
    }
  }

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between px-2 font-medium"
          onMouseDown={(event) => event.stopPropagation()}
        >
          <div className="flex min-w-0 items-center gap-2">
            <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="truncate">{activeOrg?.name ?? "Select org"}</span>
          </div>
          <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="start">
        <Command>
          <CommandInput
            placeholder="Search organisations..."
            value={query}
            onValueChange={setQuery}
          />
          <CommandList>
            {filteredOrgs.length === 0 ? (
              <div className="px-3 py-6 text-sm text-muted-foreground">No organisations found.</div>
            ) : (
              <CommandGroup>
                {filteredOrgs.map((org) => (
                  <CommandItem
                    key={org.id}
                    value={org.name}
                    onSelect={() => switchOrg(org.id)}
                    className="gap-2"
                  >
                    <Check
                      className={cn("h-4 w-4", org.id === orgId ? "opacity-100" : "opacity-0")}
                    />
                    <span className="truncate">{org.name}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
