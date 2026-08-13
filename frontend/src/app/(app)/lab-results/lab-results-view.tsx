"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Calendar, Check, Sparkles, TrendingDown, TrendingUp } from "lucide-react";

import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { Sparkline } from "@/components/sparkline";
import { labResults, labTrendExplanation, timelineRange } from "@/lib/data";
import { cn } from "@/lib/utils";
import type { LabResult } from "@/lib/types";

const CHIPS: FilterChip[] = [
  { value: "all", label: "All tests" },
  { value: "out-of-range", label: "Outside reference range" },
  { value: "trending", label: "Trending" },
];

const SEVERITY_PILL: Record<LabResult["severity"], string> = {
  ok: "bg-status-ok-bg text-status-ok",
  medium: "bg-risk-med-bg text-risk-med",
  high: "bg-risk-high-bg text-risk-high",
};

const SEVERITY_SLOT: Record<LabResult["severity"], string> = {
  ok: "bg-status-ok-bg text-status-ok",
  medium: "bg-risk-med-bg text-risk-med",
  high: "bg-risk-high-bg text-risk-high",
};

const SEVERITY_INK: Record<LabResult["severity"], string> = {
  ok: "text-status-ok",
  medium: "text-risk-med",
  high: "text-risk-high",
};

function TrendIcon({ result }: { result: LabResult }) {
  const Icon =
    result.trend === "falling"
      ? TrendingDown
      : result.trend === "rising"
        ? TrendingUp
        : Check;
  return <Icon className="size-[15px]" strokeWidth={1.8} />;
}

export function LabResultsView() {
  const [filter, setFilter] = useState("all");

  const trendCards = useMemo(
    () => labResults.filter((result) => result.points.length > 1),
    []
  );

  const rows = useMemo(
    () =>
      labResults.filter((result) => {
        if (filter === "out-of-range") return result.severity !== "ok";
        if (filter === "trending") return result.points.length > 1;
        return true;
      }),
    [filter]
  );

  return (
    <div className="flex w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
      {/* toolbar (27:667) */}
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <FilterChips
          label="Filter lab results"
          chips={CHIPS}
          value={filter}
          onChange={setFilter}
        />
        <span className="flex items-center gap-2 rounded-md border border-neutral-200 bg-neutral-0 px-3.5 py-2 text-[13px] leading-[18px] font-medium text-neutral-700">
          <Calendar className="size-[15px] text-neutral-600" strokeWidth={1.8} />
          {timelineRange}
        </span>
      </div>

      {/* trend-cards (27:682) */}
      <div className="grid w-full grid-cols-1 gap-3.5 sm:grid-cols-2 xl:grid-cols-4">
        {trendCards.map((result) => (
          <div
            key={result.id}
            className="flex flex-col gap-2.5 rounded-xl border border-neutral-200 bg-neutral-0 px-4 py-3.5 shadow-card"
          >
            <div className="flex w-full items-center justify-between gap-2">
              <p className="text-sm leading-5 font-medium text-neutral-800">
                {result.name}
              </p>
              <span
                className={cn(
                  "type-overline rounded-full px-2 py-[3px]",
                  SEVERITY_PILL[result.severity]
                )}
              >
                {result.statusLabel}
              </span>
            </div>
            <p className="flex items-baseline gap-[5px]">
              <span
                className={cn("type-metric", SEVERITY_INK[result.severity])}
              >
                {result.latestValueLabel}
              </span>
              <span className="text-[13px] leading-[19px] text-neutral-500">
                {result.unit}
              </span>
            </p>
            <Sparkline points={result.points} severity={result.severity} />
            <div className="flex w-full items-start justify-between gap-2 text-xs leading-4 font-medium">
              <span className="text-neutral-500">{result.trendLabel}</span>
              <span className="text-neutral-600">Ref {result.referenceRange}</span>
            </div>
          </div>
        ))}
      </div>

      {/* results-table (27:747) */}
      <div className="w-full overflow-hidden rounded-xl border border-neutral-200 bg-neutral-0 shadow-card">
        <div className="w-full overflow-x-auto">
          <table className="w-full min-w-[1040px] border-collapse text-left">
            <thead>
              <tr className="bg-neutral-50">
                <th className="type-overline px-[18px] py-3 text-neutral-500">
                  TEST
                </th>
                <th className="type-overline w-[110px] py-3 text-neutral-500">
                  LATEST VALUE
                </th>
                <th className="type-overline w-[100px] py-3 text-neutral-500">
                  UNIT
                </th>
                <th className="type-overline w-[150px] py-3 text-neutral-500">
                  REFERENCE RANGE
                </th>
                <th className="type-overline w-[130px] py-3 text-neutral-500">
                  MEASURED
                </th>
                <th className="type-overline w-[210px] py-3 text-neutral-500">
                  SOURCE DOCUMENT
                </th>
                <th className="type-overline w-[150px] py-3 text-neutral-500">
                  STATUS
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((result) => (
                <tr
                  key={result.id}
                  className="border-t border-neutral-200 transition-colors hover:bg-neutral-50"
                >
                  <td className="px-[18px] py-3">
                    <div className="flex items-center gap-3">
                      <span
                        className={cn(
                          "flex size-8 shrink-0 items-center justify-center rounded-md",
                          SEVERITY_SLOT[result.severity]
                        )}
                      >
                        <TrendIcon result={result} />
                      </span>
                      <span className="text-[13px] leading-[18px] font-medium text-neutral-800">
                        {result.name}
                      </span>
                    </div>
                  </td>
                  <td
                    className={cn(
                      "py-3 text-[13px] leading-[18px] font-medium",
                      SEVERITY_INK[result.severity]
                    )}
                  >
                    {result.latestValueLabel}
                  </td>
                  <td className="py-3 text-[13px] leading-[19px] text-neutral-600">
                    {result.unit}
                  </td>
                  <td className="py-3 text-[13px] leading-[19px] text-neutral-600">
                    {result.referenceRange}
                  </td>
                  <td className="py-3 text-[13px] leading-[19px] text-neutral-600">
                    {result.latestDate}
                  </td>
                  <td className="py-3">
                    <Link
                      href="/documents"
                      className="text-xs leading-4 font-medium text-brand-700 hover:underline"
                    >
                      {result.sourceDocument}
                    </Link>
                  </td>
                  <td className="py-3">
                    <span
                      className={cn(
                        "inline-block rounded-full px-2.5 py-1 text-xs leading-4 font-semibold",
                        SEVERITY_PILL[result.severity]
                      )}
                    >
                      {result.statusLabel}
                    </span>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr className="border-t border-neutral-200">
                  <td colSpan={7} className="px-[18px] py-12 text-center">
                    <p className="text-sm leading-[21px] text-neutral-600">
                      No results match this filter.
                    </p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* AI EXPLANATION OF TRENDS (27:889) */}
      <div className="flex w-full items-start gap-[11px] rounded-[10px] border border-brand-200 bg-brand-50 px-4 py-3.5">
        <Sparkles
          className="size-[17px] shrink-0 text-brand-700"
          strokeWidth={1.8}
        />
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <p className="type-overline text-brand-800">AI EXPLANATION OF TRENDS</p>
          <p className="text-[13px] leading-[19px] text-neutral-700">
            {labTrendExplanation}
          </p>
        </div>
      </div>
    </div>
  );
}
