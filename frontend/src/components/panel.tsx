import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Figma: `panel · …` — white card, 1px neutral/200 border, 12px radius, Elevation/Card. */
export function Panel({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={cn(
        "flex w-full flex-col rounded-xl border border-neutral-200 bg-neutral-0 shadow-card",
        className
      )}
    >
      {children}
    </section>
  );
}

export function PanelHeader({
  title,
  subtitle,
  actions,
  className,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 border-b border-neutral-200 px-[18px] py-3.5",
        className
      )}
    >
      <div className="flex min-w-0 flex-col gap-0.5">
        <h2 className="text-base leading-6 font-semibold tracking-[-0.1px] text-neutral-900">
          {title}
        </h2>
        {subtitle && (
          <p className="text-[13px] leading-[19px] text-neutral-500">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
