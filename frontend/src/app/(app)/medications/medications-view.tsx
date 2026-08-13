"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Copy,
  Info,
  Pill,
  RefreshCw,
  ShieldAlert,
  Scale,
  type LucideIcon,
} from "lucide-react";

import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { FlagChip } from "@/components/flag-chip";
import { Button } from "@/components/ui/button";
import { api, toErrorMessage } from "@/lib/api";
import { crossCheckSummary, medications } from "@/lib/data";
import { cn } from "@/lib/utils";
import type { MedicationFlagKind } from "@/lib/types";

const CHIPS: FilterChip[] = [
  { value: "all", label: "All medications" },
  { value: "active", label: "Active" },
  { value: "stopped", label: "Discontinued" },
  { value: "flagged", label: "Flagged only" },
];

const SUMMARY_ICONS: Record<MedicationFlagKind, LucideIcon> = {
  interaction: AlertTriangle,
  allergy: ShieldAlert,
  duplicate: Copy,
  dosage: Scale,
};

export function MedicationsView() {
  const [filter, setFilter] = useState("all");
  const [rerunning, setRerunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const rows = useMemo(
    () =>
      medications.filter((medication) => {
        if (filter === "all") return true;
        if (filter === "flagged") return medication.flags.length > 0;
        return medication.status === filter;
      }),
    [filter]
  );

  async function handleRerun() {
    setRerunning(true);
    setError(null);
    try {
      await api().listCrossCheckIssues();
    } catch (caught) {
      setError(toErrorMessage(caught));
    } finally {
      setRerunning(false);
    }
  }

  return (
    <div className="flex w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
      {/* toolbar (26:579) */}
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <FilterChips
          label="Filter medications"
          chips={CHIPS}
          value={filter}
          onChange={setFilter}
        />
        <Button onClick={handleRerun} disabled={rerunning} className="gap-2">
          <RefreshCw
            className={cn("size-[15px]", rerunning && "animate-spin")}
            strokeWidth={1.8}
          />
          {rerunning ? "Re-running…" : "Re-run cross-check"}
        </Button>
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-[10px] border border-risk-high-border bg-risk-high-bg px-4 py-3 text-[13px] leading-[19px] text-risk-high"
        >
          {error}
        </p>
      )}

      {/* cross-check-summary (26:594) */}
      <div className="grid w-full grid-cols-1 gap-3.5 sm:grid-cols-2 xl:grid-cols-4">
        {crossCheckSummary.map((card) => {
          const Icon = SUMMARY_ICONS[card.id];
          const high = card.risk === "high";
          return (
            <div
              key={card.id}
              className={cn(
                "flex flex-col gap-2 rounded-xl border px-4 py-3.5",
                high
                  ? "border-risk-high-border bg-risk-high-bg"
                  : "border-risk-med-border bg-risk-med-bg"
              )}
            >
              <div className="flex items-center gap-[9px]">
                <Icon
                  className={cn(
                    "size-4 shrink-0",
                    high ? "text-risk-high" : "text-risk-med"
                  )}
                  strokeWidth={1.8}
                />
                <p
                  className={cn(
                    "type-overline",
                    high ? "text-risk-high" : "text-risk-med"
                  )}
                >
                  {card.label}
                </p>
              </div>
              <div className="flex w-full items-center gap-[9px]">
                <p
                  className={cn(
                    "text-[22px] leading-[30px] font-semibold tracking-[-0.3px]",
                    high ? "text-risk-high" : "text-risk-med"
                  )}
                >
                  {card.count}
                </p>
                <p className="flex-1 text-[13px] leading-[19px] text-neutral-600">
                  {card.detail}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* medication-table (26:633) */}
      <div className="w-full overflow-hidden rounded-xl border border-neutral-200 bg-neutral-0 shadow-card">
        <div className="w-full overflow-x-auto">
          <table className="w-full min-w-[1040px] border-collapse text-left">
            <thead>
              <tr className="bg-neutral-50">
                <th className="type-overline px-[18px] py-3 text-neutral-500">
                  MEDICATION
                </th>
                <th className="type-overline w-[100px] py-3 text-neutral-500">
                  DOSAGE
                </th>
                <th className="type-overline w-[150px] py-3 text-neutral-500">
                  FREQUENCY
                </th>
                <th className="type-overline w-[120px] py-3 text-neutral-500">
                  STARTED
                </th>
                <th className="type-overline w-[210px] py-3 text-neutral-500">
                  SOURCE DOCUMENT
                </th>
                <th className="type-overline w-[230px] py-3 text-neutral-500">
                  CROSS-CHECK
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((medication) => {
                const stopped = medication.status === "stopped";
                return (
                  <tr
                    key={medication.id}
                    className="border-t border-neutral-200 transition-colors hover:bg-neutral-50"
                  >
                    <td className="px-[18px] py-3">
                      <div className="flex items-center gap-3">
                        <span
                          className={cn(
                            "flex size-8 shrink-0 items-center justify-center rounded-md",
                            stopped ? "bg-neutral-100" : "bg-brand-50"
                          )}
                        >
                          <Pill
                            className={cn(
                              "size-[15px]",
                              stopped ? "text-neutral-500" : "text-brand-700"
                            )}
                            strokeWidth={1.8}
                          />
                        </span>
                        <span className="flex flex-col gap-0.5">
                          <span
                            className={cn(
                              "text-[13px] leading-[18px] font-medium",
                              stopped ? "text-neutral-600" : "text-neutral-800"
                            )}
                          >
                            {medication.name}
                          </span>
                          <span className="text-xs leading-4 font-medium text-neutral-500">
                            {medication.genericName}
                          </span>
                        </span>
                      </div>
                    </td>
                    <td
                      className={cn(
                        "py-3 text-[13px] leading-[18px] font-medium",
                        stopped ? "text-neutral-600" : "text-neutral-800"
                      )}
                    >
                      {medication.dosage}
                    </td>
                    <td className="py-3 text-[13px] leading-[19px] text-neutral-600">
                      {medication.frequency}
                    </td>
                    <td className="py-3 text-[13px] leading-[19px] text-neutral-600">
                      {medication.startedOn}
                    </td>
                    <td className="py-3">
                      <Link
                        href="/documents"
                        className="text-xs leading-4 font-medium text-brand-700 hover:underline"
                      >
                        {medication.sourceDocumentId}
                      </Link>
                    </td>
                    <td className="py-3">
                      {medication.flags.length === 0 ? (
                        <span className="text-xs leading-4 font-medium text-status-ok">
                          No issues found
                        </span>
                      ) : (
                        <span className="flex flex-wrap gap-1.5">
                          {medication.flags.map((flag) => (
                            <FlagChip key={flag} flag={flag} />
                          ))}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr className="border-t border-neutral-200">
                  <td colSpan={6} className="px-[18px] py-12 text-center">
                    <p className="text-sm leading-[21px] text-neutral-600">
                      No medications match this filter.
                    </p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* method note (26:787) */}
      <div className="flex w-full items-start gap-2.5 rounded-[10px] bg-neutral-50 px-4 py-3">
        <Info className="size-4 shrink-0 text-neutral-500" strokeWidth={1.8} />
        <p className="flex-1 text-[13px] leading-[19px] text-neutral-600">
          Duplicates, dosage conflicts and date comparisons are computed
          deterministically in backend code. The AI layer is used for interpreting
          medical language and explaining findings, not for arithmetic. Every flag
          links back to the source document it came from.
        </p>
      </div>
    </div>
  );
}
