"use client";

import Link from "next/link";
import { Fragment, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Calendar,
  ChevronDown,
  ChevronRight,
  FileText,
  Loader2,
  Upload,
} from "lucide-react";

import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { api } from "@/lib/api";
import { LAB_STATUS_LABELS, LAB_TREND_LABELS } from "@/lib/lab-display";
import type { LabResult, LabStatus, LabTrendDirection } from "@/lib/types";

const CHIPS: FilterChip[] = [
  { value: "all", label: "All tests" },
  { value: "out-of-range", label: "Outside reference range" },
  { value: "trending", label: "Trending" },
];

/**
 * Backend states are displayed verbatim, never collapsed into a friendlier
 * neighbour. UNKNOWN means the value or its reference range could not be read
 * unambiguously — it is not "Normal", and it is not 0.
 */
const STATUS_STYLES: Record<LabStatus, { wrap: string; text: string }> = {
  NORMAL: { wrap: "bg-status-ok-bg", text: "text-status-ok" },
  HIGH: { wrap: "bg-risk-high-bg", text: "text-risk-high" },
  LOW: { wrap: "bg-risk-low-bg", text: "text-risk-low" },
  UNKNOWN: { wrap: "bg-neutral-100", text: "text-neutral-600" },
};

const TREND_TEXT: Record<LabTrendDirection, string> = {
  INCREASING: "text-risk-med",
  DECREASING: "text-risk-low",
  STABLE: "text-neutral-700",
  INSUFFICIENT_DATA: "text-neutral-500",
};

function StatusBadge({ status }: { status: LabStatus }) {
  const s = STATUS_STYLES[status];
  return (
    <span
      className={`type-overline rounded-full px-2 py-0.5 ${s.wrap} ${s.text}`}
      title={
        status === "UNKNOWN"
          ? "This result could not be classified against a reference range."
          : undefined
      }
    >
      {LAB_STATUS_LABELS[status]}
    </span>
  );
}

export function LabResultsView() {
  const [filter, setFilter] = useState("all");
  const [results, setResults] = useState<LabResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api()
      .listLabIntelligence()
      .then((data) => {
        if (active) {
          setResults(data || []);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setError(
            err instanceof Error ? err.message : "Failed to load lab intelligence."
          );
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const rows = useMemo(
    () =>
      results.filter((result) => {
        if (filter === "all") return true;
        // Only HIGH/LOW are outside the range. UNKNOWN is not a breach — it
        // means the result could not be classified at all.
        if (filter === "out-of-range")
          return result.status === "HIGH" || result.status === "LOW";
        // A direction the backend actually established, not merely >1 point.
        if (filter === "trending")
          return result.trend === "INCREASING" || result.trend === "DECREASING";
        return true;
      }),
    [results, filter]
  );

  return (
    <div className="flex w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
      {/* toolbar */}
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <FilterChips
          label="Filter lab tests"
          chips={CHIPS}
          value={filter}
          onChange={setFilter}
        />
        <div className="flex items-center gap-2 text-xs leading-4 font-medium text-neutral-500">
          <Calendar className="size-3.5" strokeWidth={1.8} />
          <span>Timeline Range: —</span>
        </div>
      </div>

      {/* lab results table */}
      <div className="w-full overflow-hidden rounded-xl border border-neutral-200 bg-neutral-0 shadow-card">
        <div className="w-full overflow-x-auto">
          <table className="w-full min-w-[1040px] border-collapse text-left">
            <thead>
              <tr className="bg-neutral-50">
                <th className="type-overline px-[18px] py-3 text-neutral-500">
                  TEST NAME
                </th>
                <th className="type-overline w-[140px] px-0 py-3 text-neutral-500">
                  LATEST VALUE
                </th>
                <th className="type-overline w-[160px] px-0 py-3 text-neutral-500">
                  REFERENCE RANGE
                </th>
                <th className="type-overline w-[130px] px-0 py-3 text-neutral-500">
                  DATE
                </th>
                <th className="type-overline w-[150px] px-0 py-3 text-neutral-500">
                  TREND
                </th>
                <th className="type-overline w-[130px] px-0 py-3 text-neutral-500">
                  STATUS
                </th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr className="border-t border-neutral-200">
                  <td colSpan={6} className="px-[18px] py-12 text-center text-neutral-500">
                    <div className="flex items-center justify-center gap-2 text-sm">
                      <Loader2 className="size-4 animate-spin text-brand-600" />
                      Loading lab results...
                    </div>
                  </td>
                </tr>
              )}

              {!loading && error && (
                <tr className="border-t border-neutral-200">
                  <td colSpan={6} className="px-[18px] py-12 text-center">
                    <div className="flex flex-col items-center gap-1.5">
                      <AlertCircle className="size-5 text-risk-high" strokeWidth={1.8} />
                      <p className="text-sm leading-5 font-medium text-neutral-900">
                        Lab intelligence is unavailable
                      </p>
                      <p className="mx-auto max-w-md text-[13px] leading-[18px] text-neutral-600">
                        {error} No laboratory conclusions are shown while the
                        analysis cannot be reached.
                      </p>
                    </div>
                  </td>
                </tr>
              )}

              {!loading &&
                !error &&
                rows.map((result) => {
                  const isOpen = expanded === result.id;
                  return (
                    <Fragment key={result.id}>
                      <tr className="border-t border-neutral-200 transition-colors hover:bg-neutral-50">
                        <td className="px-[18px] py-[13px]">
                          <button
                            type="button"
                            onClick={() => setExpanded(isOpen ? null : result.id)}
                            aria-expanded={isOpen}
                            className="flex items-center gap-1.5 text-left text-sm font-medium text-neutral-900 hover:text-brand-700"
                          >
                            {isOpen ? (
                              <ChevronDown className="size-3.5 shrink-0" />
                            ) : (
                              <ChevronRight className="size-3.5 shrink-0" />
                            )}
                            {result.name}
                            <span className="text-[11px] font-normal text-neutral-500">
                              ({result.points.length}{" "}
                              {result.points.length === 1 ? "result" : "results"})
                            </span>
                          </button>
                        </td>
                        <td className="py-[13px] text-[13px] text-neutral-700">
                          {/* Exactly what the lab reported. A censored "<0.01"
                              is shown as written, never as a number. */}
                          {result.latestValueLabel}
                          {result.unit ? ` ${result.unit}` : ""}
                        </td>
                        <td className="py-[13px] text-[13px] text-neutral-500">
                          {result.referenceRange}
                        </td>
                        <td className="py-[13px] text-[13px] text-neutral-500">
                          {result.latestDate}
                        </td>
                        <td className={`py-[13px] text-[13px] ${TREND_TEXT[result.trend]}`}>
                          {LAB_TREND_LABELS[result.trend]}
                        </td>
                        <td className="py-[13px]">
                          <StatusBadge status={result.status} />
                        </td>
                      </tr>

                      {isOpen && (
                        <tr className="border-t border-neutral-200 bg-neutral-50">
                          <td colSpan={6} className="px-[18px] py-4">
                            <p className="type-overline mb-2 text-neutral-500">
                              HISTORICAL RESULTS
                            </p>
                            {result.points.length === 0 ? (
                              <p className="text-[13px] leading-[18px] text-neutral-600">
                                No historical results are recorded for this test.
                              </p>
                            ) : (
                              <ul className="flex flex-col gap-1.5">
                                {result.points.map((point, index) => (
                                  <li
                                    key={`${point.date}-${index}`}
                                    className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] leading-[18px]"
                                  >
                                    <span className="w-[110px] shrink-0 text-neutral-500">
                                      {point.date}
                                    </span>
                                    <span className="font-medium text-neutral-900">
                                      {point.valueLabel}
                                      {result.unit ? ` ${result.unit}` : ""}
                                    </span>
                                    <StatusBadge status={point.status} />
                                    {point.value === null && (
                                      <span className="text-[12px] text-neutral-500">
                                        No exact numeric value reported
                                      </span>
                                    )}
                                    {point.documentId && (
                                      <Link
                                        href={`/documents/${point.documentId}`}
                                        className="inline-flex items-center gap-1 text-[12px] font-medium text-brand-700 hover:underline"
                                      >
                                        <FileText className="size-3" />
                                        {point.documentName || "Source document"}
                                      </Link>
                                    )}
                                  </li>
                                ))}
                              </ul>
                            )}
                            {result.trend === "INSUFFICIENT_DATA" && (
                              <p className="mt-2.5 text-[12px] leading-[16px] text-neutral-500">
                                Not enough numeric results to establish a
                                direction. No trend is claimed for this test.
                              </p>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}

              {!loading && !error && rows.length === 0 && (
                <tr className="border-t border-neutral-200">
                  <td colSpan={6} className="px-[18px] py-12 text-center">
                    <p className="text-sm leading-[21px] text-neutral-600">
                      {results.length === 0
                        ? "No lab results found. Upload a lab report to automatically extract and trend biomarker values."
                        : "No lab tests match this filter."}
                    </p>
                    {results.length === 0 && (
                      <Link
                        href="/documents/upload"
                        className="mt-2 inline-flex items-center gap-1.5 text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                      >
                        <Upload className="size-3.5" />
                        Upload lab report
                      </Link>
                    )}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
