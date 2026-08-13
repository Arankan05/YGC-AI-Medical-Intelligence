import { ShieldCheck } from "lucide-react";

import { providerAttribution } from "@/lib/data";
import { cn } from "@/lib/utils";

/** Figma: `panel · attribution` (node 33:1239). */
export function ProviderAttribution({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex w-full flex-col gap-2 rounded-xl border border-brand-200 bg-sidebar-bg px-4 py-3.5",
        className
      )}
    >
      <div className="flex items-center gap-[9px]">
        <ShieldCheck
          className="size-4 shrink-0 text-brand-700"
          strokeWidth={1.8}
        />
        <p className="type-overline text-brand-700">
          {providerAttribution.overline}
        </p>
      </div>
      <p className="text-[13px] leading-[19px] text-sidebar-ink-muted">
        {providerAttribution.body}
      </p>
      <p className="text-xs leading-4 font-medium text-sidebar-ink-dim">
        {providerAttribution.credit}
      </p>
    </div>
  );
}
