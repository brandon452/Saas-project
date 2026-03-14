import * as React from "react"

import { cn } from "@/lib/utils"

type CommandInputProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange"> & {
  onValueChange?: (value: string) => void
}

export function Command({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col">{children}</div>
}

export function CommandInput({ className, onValueChange, ...props }: CommandInputProps) {
  return (
    <div className="border-b border-border p-2">
      <input
        className={cn(
          "w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring",
          className,
        )}
        onChange={(event) => onValueChange?.(event.target.value)}
        {...props}
      />
    </div>
  )
}

export function CommandList({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return <div className={cn("max-h-72 overflow-y-auto", className)}>{children}</div>
}

export function CommandGroup({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return <div className={cn("p-1", className)}>{children}</div>
}

export function CommandItem({
  children,
  className,
  value,
  onSelect,
}: {
  children: React.ReactNode
  className?: string
  value: string
  onSelect?: (value: string) => void
}) {
  return (
    <button
      type="button"
      className={cn(
        "flex w-full items-center rounded-md px-2 py-2 text-left text-sm hover:bg-accent hover:text-accent-foreground",
        className,
      )}
      onClick={() => onSelect?.(value)}
    >
      {children}
    </button>
  )
}
