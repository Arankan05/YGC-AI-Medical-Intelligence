"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowDownWideNarrow, FileText, MapPin } from "lucide-react";

import { RiskBadge } from "@/components/risk-badge";
import { Button } from "@/components/ui/button";
import { findings, findingsSortLabel, recordTotals } from "@/lib/data";
import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/lib/types";

const RISK_ORDER: RiskLevel[] = ["high", "medium", "low"];

export function FindingsView() {
  const [filter, setFilter] = useState<RiskLevel | "all">("all");

  /** Counts come from the record totals in the design, not the visible page. */
  const counts = {
    all: recordTotals.findings,
    ...recordTotals.findingsByRisk,
  };

  const sorted = useMemo(
    () =>
      [...findings]
        .filter((finding) => filter === "all" || finding.risk === filter)
        .sort(
          (a, b) =>
            RISK_ORDER.indexOf(a.risk) - RISK_ORDER.indexOf(b.risk) ||
            b.confidence - a.confidence
        ),
    [filter]
  );

  const chips: { value: RiskLevel | "all"; label: string; dot?: string }[] = [
    { value: "all", label: `All findings · ${counts.all}` },
    { value: "high", label: `High · ${counts.high}`, dot: "bg-risk-high" },
    { value: "medium", label: `Medium · ${counts.medium}`, dot: "bg-risk-med" },
    { value: "low", label: `Low · ${counts.low}`, dot: "bg-risk-low" },
  ];

  return (
    <div className="flex w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
      {/* toolbar (28:755) */}
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <div role="tablist" aria-label="Filter findings by risk" className="flex flex-wrap gap-2">
          {chips.map((chip) => {
            const active = chip.value === filter;
            return (
              <button
                key={chip.value}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setFilter(chip.value)}
                className={cn(
                  "flex cursor-pointer items-center gap-[7px] rounded-full px-3.5 py-2 text-[13px] leading-[18px] font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-brand-700/25",
                  active
                    ? "bg-sidebar-active-bg text-sidebar-active-ink"
                    : "border border-neutral-200 bg-neutral-0 text-neutral-600 hover:bg-neutral-50"
                )}
              >
                {chip.dot && !active && (
                  <span className={cn("size-[7px] rounded-full", chip.dot)} />
                )}
                {chip.label}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2 rounded-md border border-neutral-200 bg-neutral-0 px-3.5 py-2 text-[13px] leading-[18px] font-medium text-neutral-700">
          {findingsSortLabel}
          <ArrowDownWideNarrow
            className="size-[15px] text-neutral-600"
            strokeWidth={1.8}
          />
        </div>
      </div>

      {/* findings-list (28:772) */}
      <div className="flex w-full flex-col gap-3.5">
        {sorted.length === 0 && (
          <p className="rounded-xl border border-neutral-200 bg-neutral-0 py-16 text-center text-sm leading-[21px] text-neutral-600 shadow-card">
            No findings at this risk level.
          </p>
        )}
        {sorted.map((finding) => {
          const high = finding.risk === "high";
          return (
            <article
              key={finding.id}
              className={cn(
                "flex w-full flex-col gap-[11px] rounded-xl border px-[18px] py-[15px] shadow-card",
                high
                  ? "border-risk-high-border bg-risk-high-bg"
                  : "border-neutral-200 bg-neutral-0"
              )}
            >
              <div className="flex w-full flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-[11px]">
                  <RiskBadge risk={finding.risk} />
                  <h2 className="text-base leading-6 font-semibold tracking-[-0.1px] text-neutral-900">
                    {finding.title}
                  </h2>
                  <span className="type-overline rounded-sm bg-neutral-100 px-2 py-[3px] text-neutral-600">
                    {finding.categoryLabel}
                  </span>
                </div>
                <span className="text-xs leading-4 font-medium text-sidebar-ink-muted">
                  Detected {finding.detectedOn}
                </span>
              </div>

              <p className="text-sm leading-[21px] text-neutral-700">
                {finding.summary}
              </p>

              <div className="flex w-full flex-col gap-2 rounded-[10px] border border-neutral-200 bg-neutral-0 px-3.5 py-3">
                <p className="type-overline text-neutral-500">
                  EVIDENCE FROM YOUR RECORDS
                </p>
                {finding.evidence.map((evidence) => (
                  <div
                    key={evidence.id}
                    className="flex w-full flex-wrap items-center gap-2.5"
                  >
                    <FileText
                      className="size-3.5 shrink-0 text-brand-700"
                      strokeWidth={1.8}
                    />
                    <Link
                      href="/documents"
                      className="text-xs leading-4 font-semibold text-brand-700 hover:underline"
                    >
                      {evidence.documentTitle} · p{evidence.page}
                    </Link>
                    <p className="min-w-0 flex-1 text-[13px] leading-[19px] text-neutral-600">
                      {evidence.quote}
                    </p>
                  </div>
                ))}
              </div>

              <div className="flex w-full flex-wrap items-center justify-between gap-3 pt-0.5">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="text-xs leading-4 font-medium text-neutral-500">
                    Confidence
                  </span>
                  <span className="h-1.5 w-[130px] overflow-hidden rounded-full bg-neutral-200">
                    <span
                      className={cn(
                        "block h-1.5 rounded-full",
                        high ? "bg-risk-high" : "bg-risk-med"
                      )}
                      style={{ width: `${finding.confidence}%` }}
                    />
                  </span>
                  <span className="text-xs leading-4 font-semibold text-neutral-700">
                    {finding.confidence}%
                  </span>
                  <span className="h-3.5 w-px bg-neutral-300" />
                  <span className="text-xs leading-4 font-medium text-neutral-600">
                    {finding.guidance}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-2.5">
                  <Button
                    render={<Link href={`/findings/${finding.id}`} />}
                    variant="outline"
                    size="sm"
                    className="px-3.5 py-[9px]"
                  >
                    View full finding
                  </Button>
                  <Button
                    render={<Link href="/providers" />}
                    variant={finding.providerCta.primary ? "default" : "outline"}
                    size="sm"
                    className="gap-2 px-3.5 py-[9px]"
                  >
                    <MapPin className="size-3.5" strokeWidth={1.8} />
                    {finding.providerCta.label}
                  </Button>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
