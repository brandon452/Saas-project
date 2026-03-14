"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

type PopoverContextValue = {
  open: boolean
  setOpen: (open: boolean) => void
}

const PopoverContext = React.createContext<PopoverContextValue | null>(null)

function usePopoverContext() {
  const context = React.useContext(PopoverContext)
  if (!context) {
    throw new Error("Popover components must be used within Popover")
  }
  return context
}

export function Popover({
  children,
  open,
  onOpenChange,
}: {
  children: React.ReactNode
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  return (
    <PopoverContext.Provider value={{ open, setOpen: onOpenChange }}>
      <div className="relative">{children}</div>
    </PopoverContext.Provider>
  )
}

export function PopoverTrigger({
  children,
  asChild,
}: {
  children: React.ReactElement
  asChild?: boolean
}) {
  const { open, setOpen } = usePopoverContext()

  if (asChild && React.isValidElement(children)) {
    const child = children as React.ReactElement<{
      onClick?: (event: React.MouseEvent) => void
    }>

    return React.cloneElement(child, {
      onClick: (event: React.MouseEvent) => {
        child.props.onClick?.(event)
        setOpen(!open)
      },
    })
  }

  return <button onClick={() => setOpen(!open)}>{children}</button>
}

export function PopoverContent({
  children,
  className,
}: {
  children: React.ReactNode
  align?: "start" | "center" | "end"
  className?: string
}) {
  const { open, setOpen } = usePopoverContext()
  const ref = React.useRef<HTMLDivElement | null>(null)

  React.useEffect(() => {
    if (!open) return

    function handlePointerDown(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener("mousedown", handlePointerDown)
    return () => document.removeEventListener("mousedown", handlePointerDown)
  }, [open, setOpen])

  if (!open) return null

  return (
    <div
      ref={ref}
      className={cn(
        "absolute left-0 top-full z-50 mt-2 rounded-md border border-border bg-popover p-4 text-popover-foreground shadow-lg",
        className,
      )}
    >
      {children}
    </div>
  )
}
