import type { LabStatus, LabTrendDirection } from "@/lib/types";

/**
 * The single source of truth for how backend laboratory states are worded.
 *
 * Shared so that every view spells them the same way. Two independent copies
 * of these maps is how "INSUFFICIENT_DATA" ends up reading as "Stable" in one
 * screen and "Insufficient data" in another — a difference that changes what
 * the interface claims about a patient.
 *
 * Each backend state maps to exactly one label. Nothing collapses into a
 * neighbouring state, and UNKNOWN is never rendered as normal or as 0.
 */
export const LAB_STATUS_LABELS: Record<LabStatus, string> = {
  NORMAL: "Normal",
  HIGH: "High",
  LOW: "Low",
  UNKNOWN: "Unknown",
};

export const LAB_TREND_LABELS: Record<LabTrendDirection, string> = {
  INCREASING: "Increasing",
  DECREASING: "Decreasing",
  STABLE: "Stable",
  INSUFFICIENT_DATA: "Insufficient data",
};
