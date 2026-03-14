"use client"

import * as React from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type AlertDialogContextValue = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const AlertDialogContext = React.createContext<AlertDialogContextValue | null>(null)

function useAlertDialogContext() {
  const context = React.useContext(AlertDialogContext)
  if (!context) {
    throw new Error("AlertDialog components must be used within AlertDialog")
  }
  return context
}

export function AlertDialog({
  open,
  onOpenChange,
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
}) {
  return (
    <AlertDialogContext.Provider value={{ open, onOpenChange }}>
      {children}
    </AlertDialogContext.Provider>
  )
}

export function AlertDialogContent({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  const { open, onOpenChange } = useAlertDialogContext()

  React.useEffect(() => {
    if (!open) return

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onOpenChange(false)
    }

    document.addEventListener("keydown", handleEscape)
    return () => document.removeEventListener("keydown", handleEscape)
  }, [open, onOpenChange])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className={cn("w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl", className)}>
        {children}
      </div>
    </div>
  )
}

export function AlertDialogHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-2", className)} {...props} />
}

export function AlertDialogTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("text-lg font-semibold", className)} {...props} />
}

export function AlertDialogDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-muted-foreground", className)} {...props} />
}

export function AlertDialogFooter({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mt-6 flex justify-end gap-3", className)} {...props} />
}

export function AlertDialogCancel({
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const { onOpenChange } = useAlertDialogContext()

  return (
    <Button
      variant="ghost"
      className={className}
      onClick={(event) => {
        props.onClick?.(event)
        onOpenChange(false)
      }}
      {...props}
    />
  )
}

export function AlertDialogAction({
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const { onOpenChange } = useAlertDialogContext()

  return (
    <Button
      className={className}
      onClick={(event) => {
        props.onClick?.(event)
        onOpenChange(false)
      }}
      {...props}
    />
  )
}
