import { AlertTriangle, Activity, FileText, Flag, Pill } from "lucide-react";

import { cn } from "@/lib/utils";
import type { DashboardMetric } from "@/lib/types";

/**
 * Figma: Design System / Metric Card (node 19:62)
 * Pick a Kind for the icon/accent, then override label, value and delta text.
 */
const KIND_STYLES: Record<
  DashboardMetric["kind"],
  { slot: string; icon: typeof FileText; iconColor: string; deltaInk?: string }
> = {
  documents: { slot: "bg-brand-50", icon: FileText, iconColor: "text-brand-700" },
  events: { slot: "bg-brand-50", icon: Activity, iconColor: "text-brand-700" },
  medications: {
    slot: "bg-status-info-bg",
    icon: Pill,
    iconColor: "text-status-info",
  },
  findings: {
    slot: "bg-risk-med-bg",
    icon: AlertTriangle,
    iconColor: "text-risk-med",
  },
  // 19:50 — flag glyph, and the delta reads in risk/high on the dashboard.
  priority: {
    slot: "bg-risk-high-bg",
    icon: Flag,
    iconColor: "text-risk-high",
    deltaInk: "text-risk-high",
  },
};

export function MetricCard({
  metric,
  muted = false,
  className,
}: {
  metric: DashboardMetric;
  /** First-run state (Figma 39:1611) — dimmed tile with an em dash value. */
  muted?: boolean;
  className?: string;
}) {
  const s = KIND_STYLES[metric.kind];
  const Icon = s.icon;
  return (
    <div
      className={cn(
        // 19:2 — fixed 116px frame: 16px above the row, content ends 5px shy of the base.
        "flex h-[116px] flex-col gap-1.5 rounded-xl border border-neutral-200 bg-neutral-0 px-[18px] pt-4 shadow-card",
        muted && "opacity-85",
        className
      )}
    >
      <div className="flex w-full items-center justify-between gap-3">
        <p
          className={cn(
            "type-overline whitespace-nowrap",
            muted ? "text-neutral-600" : "text-neutral-500"
          )}
        >
          {metric.label}
        </p>
        <span
          className={cn(
            "flex size-7 shrink-0 items-center justify-center rounded-md",
            s.slot
          )}
        >
          <Icon className={cn("size-[15px]", s.iconColor)} strokeWidth={2} />
        </span>
      </div>
      <p
        className={cn(
          "type-metric",
          muted ? "text-neutral-600" : "text-neutral-900"
        )}
      >
        {metric.value}
      </p>
      <p
        className={cn(
          "text-[13px] leading-[19px]",
          muted
            ? "text-neutral-600"
            : (s.deltaInk ?? "text-neutral-500")
        )}
      >
        {metric.delta}
      </p>
    </div>
  );
}
