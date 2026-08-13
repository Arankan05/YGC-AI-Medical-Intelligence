import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Figma: Design System / Button (node 11:33)
 * Primary for main actions, Danger reserved for destructive actions only.
 */
const buttonVariants = cva(
  "group/button inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 rounded-md border border-transparent bg-clip-padding text-sm leading-5 font-medium whitespace-nowrap transition-colors outline-none select-none focus-visible:ring-3 focus-visible:ring-ring/25 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        // Type=Primary
        default: "bg-brand-700 text-neutral-0 hover:bg-brand-700/90",
        // Type=Secondary
        outline:
          "border-neutral-300 bg-neutral-0 text-neutral-700 hover:bg-neutral-50",
        secondary:
          "border-neutral-300 bg-neutral-0 text-neutral-700 hover:bg-neutral-50",
        // Type=Ghost
        ghost: "bg-neutral-100 text-neutral-600 hover:bg-neutral-200",
        // Type=Danger
        destructive: "bg-risk-high text-neutral-0 hover:bg-risk-high/90",
        subtle:
          "bg-brand-50 text-brand-700 hover:bg-brand-100 border-brand-200",
        link: "text-brand-700 underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-[18px]",
        sm: "h-[34px] rounded-md px-3 text-[13px] [&_svg:not([class*='size-'])]:size-3.5",
        xs: "h-7 rounded-md px-2.5 text-xs [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-[46px] px-5",
        icon: "size-10",
        "icon-sm": "size-[34px] rounded-md",
        "icon-xs": "size-7 rounded-md",
        "icon-lg": "size-[38px] rounded-md",
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
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
