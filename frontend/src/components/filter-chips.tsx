"use client";

import { cn } from "@/lib/utils";

export interface FilterChip {
  value: string;
  label: string;
}

/** Figma: `toolbar` chip row (nodes 23:488, 26:492, 28:668) — pill filters. */
export function FilterChips({
  chips,
  value,
  onChange,
  label,
  className,
}: {
  chips: FilterChip[];
  value: string;
  onChange: (value: string) => void;
  label: string;
  className?: string;
}) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className={cn("flex flex-wrap items-center gap-2", className)}
    >
      {chips.map((chip) => {
        const active = chip.value === value;
        return (
          <button
            key={chip.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(chip.value)}
            className={cn(
              // Figma chip is 34px tall either way — the border eats 2px of the padding.
              "cursor-pointer rounded-full px-3.5 text-[13px] leading-[18px] font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-brand-700/25",
              active
                ? "bg-sidebar-active-bg py-2 text-sidebar-active-ink"
                : "border border-neutral-200 bg-neutral-0 py-[7px] text-neutral-600 hover:bg-neutral-50"
            )}
          >
            {chip.label}
          </button>
        );
      })}
    </div>
  );
}
