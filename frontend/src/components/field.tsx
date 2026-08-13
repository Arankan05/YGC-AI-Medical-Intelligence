import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Figma: `field` group — Label/12 Semi (uppercase) above a 44px input. */
export function Field({
  label,
  htmlFor,
  hint,
  error,
  className,
  children,
}: {
  label: string;
  htmlFor?: string;
  hint?: string;
  error?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("flex w-full flex-col gap-[7px]", className)}>
      <label
        htmlFor={htmlFor}
        className="text-xs leading-4 font-semibold text-neutral-700"
      >
        {label}
      </label>
      {children}
      {error ? (
        <p className="text-[13px] leading-[18px] text-risk-high">{error}</p>
      ) : hint ? (
        <p className="text-[13px] leading-[18px] text-neutral-500">{hint}</p>
      ) : null}
    </div>
  );
}

export const fieldInputClass =
  "h-11 w-full rounded-md border border-neutral-300 bg-neutral-0 px-3.5 text-sm leading-[21px] text-neutral-900 outline-none transition-colors placeholder:text-neutral-600 focus:border-brand-700 focus:ring-3 focus:ring-brand-700/15 disabled:cursor-not-allowed disabled:bg-neutral-50 aria-[invalid=true]:border-risk-high";
