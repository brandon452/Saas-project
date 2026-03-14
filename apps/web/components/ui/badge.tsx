import * as React from "react"

import { cn } from "@/lib/utils"

type BadgeVariant = "default" | "secondary" | "destructive" | "outline"

export function Badge({
  className,
  children,
  variant = "secondary",
}: {
  className?: string
  children: React.ReactNode
  variant?: BadgeVariant
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        variant === "default" && "border-primary bg-primary text-primary-foreground",
        variant === "secondary" && "border-secondary bg-secondary text-secondary-foreground",
        variant === "destructive" &&
          "border-red-200 bg-red-100 text-red-700",
        variant === "outline" && "border-border bg-transparent text-foreground",
        className,
      )}
    >
      {children}
    </span>
  )
}
