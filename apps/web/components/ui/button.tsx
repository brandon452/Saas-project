import * as React from "react"

import { cn } from "@/lib/utils"

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "ghost" | "outline" | "destructive"
  size?: "sm" | "md" | "lg"
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "md", type = "button", ...props }, ref) => {
    return (
      <button
        ref={ref}
        type={type}
        className={cn(
          "inline-flex items-center gap-2 rounded-md text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
          size === "sm" && "h-8 px-2.5 py-1.5 text-xs",
          size === "md" && "h-9 px-3 py-2 text-sm",
          size === "lg" && "h-10 px-4 py-2 text-sm",
          variant === "default" && "bg-primary text-primary-foreground hover:opacity-95",
          variant === "ghost" && "hover:bg-accent hover:text-accent-foreground",
          variant === "outline" && "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
          variant === "destructive" && "border border-red-300 text-red-600 hover:border-red-400 hover:bg-red-50 hover:text-red-700",
          className,
        )}
        {...props}
      />
    )
  },
)

Button.displayName = "Button"
