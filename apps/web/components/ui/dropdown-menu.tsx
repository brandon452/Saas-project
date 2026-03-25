"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

type DropdownMenuContextValue = {
  open: boolean
  setOpen: React.Dispatch<React.SetStateAction<boolean>>
  triggerRef: React.MutableRefObject<HTMLElement | null>
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
  const triggerRef = React.useRef<HTMLElement | null>(null)

  return (
    <DropdownMenuContext.Provider value={{ open, setOpen, triggerRef }}>
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
  const { open, setOpen, triggerRef } = useDropdownMenuContext()

  const handleClick = () => setOpen(!open)

  const child =
    asChild && React.isValidElement(children)
      ? React.cloneElement(children as React.ReactElement<{ onClick?: (e: React.MouseEvent) => void }>, {
          onClick: (e: React.MouseEvent) => {
            ;(children.props as { onClick?: (e: React.MouseEvent) => void }).onClick?.(e)
            handleClick()
          },
        })
      : <button onClick={handleClick}>{children}</button>

  return (
    <span ref={triggerRef as React.MutableRefObject<HTMLSpanElement>} style={{ display: "contents" }}>
      {child}
    </span>
  )
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
  const { open, setOpen, triggerRef } = useDropdownMenuContext()
  const ref = React.useRef<HTMLDivElement | null>(null)

  React.useEffect(() => {
    if (!open) return

    function handlePointerDown(event: MouseEvent) {
      const target = event.target as Node
      if (
        ref.current &&
        !ref.current.contains(target) &&
        triggerRef.current &&
        !triggerRef.current.contains(target)
      ) {
        setOpen(false)
      }
    }

    document.addEventListener("mousedown", handlePointerDown)
    return () => document.removeEventListener("mousedown", handlePointerDown)
  }, [open, setOpen, triggerRef])

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
