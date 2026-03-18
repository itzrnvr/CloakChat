import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-[var(--color-base-900)] text-[var(--color-base-50)] hover:bg-[var(--color-base-800)] dark:bg-[var(--color-base-50)] dark:text-[var(--color-base-950)] dark:hover:bg-[var(--color-base-200)]",
        destructive:
          "bg-[var(--color-red-400)] text-white hover:bg-[var(--color-red-400)]/90",
        outline:
          "border border-[var(--color-base-300)] bg-transparent hover:bg-[var(--color-base-100)] text-[var(--color-base-900)] dark:border-[var(--color-base-700)] dark:text-[var(--color-base-200)] dark:hover:bg-[var(--color-base-800)]",
        secondary:
          "bg-[var(--color-base-200)] text-[var(--color-base-900)] hover:bg-[var(--color-base-300)] dark:bg-[var(--color-base-800)] dark:text-[var(--color-base-50)] dark:hover:bg-[var(--color-base-700)]",
        ghost: "hover:bg-[var(--color-base-100)] hover:text-[var(--color-base-900)] dark:hover:bg-[var(--color-base-800)] dark:hover:text-[var(--color-base-50)]",
        link: "text-[var(--color-base-900)] underline-offset-4 hover:underline dark:text-[var(--color-base-50)]",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

// eslint-disable-next-line react-refresh/only-export-components
export { Button, buttonVariants }
