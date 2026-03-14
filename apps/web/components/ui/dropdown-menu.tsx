"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

type DropdownMenuContextValue = {
  open: boolean
  setOpen: React.Dispatch<React.SetStateAction<boolean>>
}

const DropdownMenuContext = React.createContext<DropdownMenuContextValue | null>(null)

function useDropdownMenuContext() {
  const context = React.useContext(DropdownMenuContext)
  if (!context) {
    throw new Error("DropdownMenu components must be used within DropdownMenu")
  }
  return context
}

export function DropdownMenu({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false)

  return (
    <DropdownMenuContext.Provider value={{ open, setOpen }}>
      <div className="relative">{children}</div>
    </DropdownMenuContext.Provider>
  )
}

export function DropdownMenuTrigger({
  children,
  asChild,
}: {
  children: React.ReactElement
  asChild?: boolean
}) {
  const { open, setOpen } = useDropdownMenuContext()

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

export function DropdownMenuContent({
  children,
  className,
}: {
  children: React.ReactNode
  side?: "top" | "bottom"
  align?: "start" | "end"
  className?: string
}) {
  const { open, setOpen } = useDropdownMenuContext()
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
        "absolute bottom-full left-0 z-50 mb-2 rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-lg",
        className,
      )}
    >
      {children}
    </div>
  )
}

export function DropdownMenuItem({
  children,
  className,
  onClick,
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const { setOpen } = useDropdownMenuContext()

  return (
    <button
      type="button"
      className={cn(
        "flex w-full items-center rounded-sm px-2 py-2 text-sm hover:bg-accent hover:text-accent-foreground",
        className,
      )}
      onClick={(event) => {
        onClick?.(event)
        setOpen(false)
      }}
    >
      {children}
    </button>
  )
}
