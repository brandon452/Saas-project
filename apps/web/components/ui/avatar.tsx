import * as React from "react"

import { cn } from "@/lib/utils"

export function Avatar({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-secondary text-secondary-foreground",
        className,
      )}
      {...props}
    />
  )
}

export function AvatarFallback({
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("font-medium", className)} {...props} />
}
