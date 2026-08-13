import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/lib/types";

/**
 * Figma: Design System / Risk Badge (node 11:11)
 * LOW = informational, MEDIUM = raise with a professional, HIGH = prompt consultation.
 */
const RISK_STYLES: Record<
  RiskLevel,
  { wrap: string; dot: string; text: string; label: string }
> = {
  high: {
    wrap: "bg-risk-high-bg border-risk-high-border",
    dot: "bg-risk-high",
    text: "text-risk-high",
    label: "HIGH RISK",
  },
  medium: {
    wrap: "bg-risk-med-bg border-risk-med-border",
    dot: "bg-risk-med",
    text: "text-risk-med",
    label: "MEDIUM RISK",
  },
  low: {
    wrap: "bg-risk-low-bg border-risk-low-border",
    dot: "bg-risk-low",
    text: "text-risk-low",
    label: "LOW RISK",
  },
};

export function RiskBadge({
  risk,
  label,
  className,
}: {
  risk: RiskLevel;
  label?: string;
  className?: string;
}) {
  const s = RISK_STYLES[risk];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border py-1 pr-2.5 pl-2",
        s.wrap,
        className
      )}
    >
      <span className={cn("size-1.5 shrink-0 rounded-full", s.dot)} />
      <span className={cn("type-overline", s.text)}>{label ?? s.label}</span>
    </span>
  );
}
