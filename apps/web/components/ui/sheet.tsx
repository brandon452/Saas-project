"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

type SheetContextValue = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const SheetContext = React.createContext<SheetContextValue | null>(null)

function useSheetContext() {
  const context = React.useContext(SheetContext)
  if (!context) {
    throw new Error("Sheet components must be used within Sheet")
  }
  return context
}

export function Sheet({
  open,
  onOpenChange,
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
}) {
  return <SheetContext.Provider value={{ open, onOpenChange }}>{children}</SheetContext.Provider>
}

export function SheetContent({
  children,
  className,
  side = "right",
}: {
  children: React.ReactNode
  className?: string
  side?: "right" | "left"
}) {
  const { open, onOpenChange } = useSheetContext()

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 bg-black/40">
      <button
        type="button"
        aria-label="Close panel"
        className="absolute inset-0"
        onClick={() => onOpenChange(false)}
      />
      <div
        className={cn(
          "absolute top-0 h-full w-full max-w-xl overflow-y-auto border-l border-border bg-card p-6 shadow-xl",
          side === "right" ? "right-0" : "left-0 border-l-0 border-r",
          className,
        )}
      >
        {children}
      </div>
    </div>
  )
}

export function SheetHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-2", className)} {...props} />
}

export function SheetTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("text-lg font-semibold", className)} {...props} />
}

export function SheetDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-muted-foreground", className)} {...props} />
}
