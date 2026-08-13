import { cn } from "@/lib/utils";
import type { MedicationFlagKind, RiskLevel } from "@/lib/types";

/** Figma: CROSS-CHECK cell chips (node 26:664 and siblings). */
export const FLAG_META: Record<
  MedicationFlagKind,
  { label: string; risk: RiskLevel }
> = {
  interaction: { label: "Interaction", risk: "high" },
  allergy: { label: "Allergy contradiction", risk: "high" },
  duplicate: { label: "Duplicate", risk: "medium" },
  dosage: { label: "Dosage conflict", risk: "medium" },
};

const RISK_CHIP: Record<RiskLevel, string> = {
  high: "bg-risk-high-bg text-risk-high",
  medium: "bg-risk-med-bg text-risk-med",
  low: "bg-risk-low-bg text-risk-low",
};

export function FlagChip({
  flag,
  className,
}: {
  flag: MedicationFlagKind;
  className?: string;
}) {
  const meta = FLAG_META[flag];
  return (
    <span
      className={cn(
        "type-overline inline-block rounded-full px-2 py-[3px]",
        RISK_CHIP[meta.risk],
        className
      )}
    >
      {meta.label}
    </span>
  );
}
