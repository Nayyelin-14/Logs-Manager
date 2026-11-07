import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-[4px] text-[13px] font-medium transition-[background-color,border-color,color,box-shadow,transform] duration-150 outline-none disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4 focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/20 aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40",
  {
    variants: {
      variant: {
        default:
          "bg-ink text-canvas shadow-[0_1px_2px_rgba(16,24,40,0.10)] hover:bg-rail active:translate-y-px",
        destructive:
          "bg-critical text-white shadow-[0_1px_2px_rgba(16,24,40,0.10)] hover:bg-critical/90 focus-visible:ring-critical/20 active:translate-y-px",
        outline:
          "border border-border bg-card text-ink hover:border-ink/20 hover:bg-surface-muted active:translate-y-px",
        secondary:
          "bg-surface-muted text-ink hover:bg-border active:translate-y-px",
        signal:
          "bg-signal text-signal-ink shadow-[0_1px_2px_rgba(16,24,40,0.08)] hover:bg-signal-hover active:translate-y-px",
        ghost:
          "text-ink-muted hover:bg-surface-muted hover:text-ink dark:hover:bg-accent/50",
        link: "text-brand underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-3.5 py-2 has-[>svg]:px-3",
        sm: "h-8 rounded-sm gap-1.5 px-2.5 has-[>svg]:px-2",
        lg: "h-10 rounded-[4px] px-5 has-[>svg]:px-4",
        icon: "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot : "button"

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export { Button, buttonVariants }
