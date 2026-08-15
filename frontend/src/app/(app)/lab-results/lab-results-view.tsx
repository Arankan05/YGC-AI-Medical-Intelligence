"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Calendar, Loader2, Upload } from "lucide-react";

import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { api } from "@/lib/api";
import type { LabResult } from "@/lib/types";

const CHIPS: FilterChip[] = [
  { value: "all", label: "All tests" },
  { value: "out-of-range", label: "Outside reference range" },
  { value: "trending", label: "Trending" },
];

export function LabResultsView() {
  const [filter, setFilter] = useState("all");
  const [results, setResults] = useState<LabResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    api()
      .listLabResults()
      .then((data) => {
        if (active) {
          setResults(data || []);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const rows = useMemo(
    () =>
      results.filter((result) => {
        if (filter === "all") return true;
        if (filter === "out-of-range") return result.severity !== "ok";
        if (filter === "trending") return result.points && result.points.length > 1;
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
          <table className="w-full min-w-[920px] border-collapse text-left">
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
                <th className="type-overline w-[140px] px-0 py-3 text-neutral-500">
                  DATE
                </th>
                <th className="type-overline w-[160px] px-0 py-3 text-neutral-500">
                  STATUS
                </th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr className="border-t border-neutral-200">
                  <td colSpan={5} className="px-[18px] py-12 text-center text-neutral-500">
                    <div className="flex items-center justify-center gap-2 text-sm">
                      <Loader2 className="size-4 animate-spin text-brand-600" />
                      Loading lab results...
                    </div>
                  </td>
                </tr>
              )}

              {!loading &&
                rows.map((result) => (
                  <tr
                    key={result.id}
                    className="border-t border-neutral-200 transition-colors hover:bg-neutral-50"
                  >
                  <td className="px-[18px] py-[13px] text-sm font-medium text-neutral-900">
                    {result.name}
                  </td>
                  <td className="py-[13px] text-[13px] text-neutral-700">
                    {result.latestValueLabel || result.latestValue} {result.unit}
                  </td>
                  <td className="py-[13px] text-[13px] text-neutral-500">
                    {result.referenceRange}
                  </td>
                  <td className="py-[13px] text-[13px] text-neutral-500">
                    {result.latestDate}
                  </td>
                  <td className="py-[13px]">
                    <span className="type-overline rounded-full bg-status-ok-bg px-2 py-0.5 text-status-ok">
                      {result.statusLabel || "NORMAL"}
                    </span>
                  </td>
                </tr>
              ))}

              {!loading && rows.length === 0 && (
                <tr className="border-t border-neutral-200">
                  <td colSpan={5} className="px-[18px] py-12 text-center">
                    <p className="text-sm leading-[21px] text-neutral-600">
                      No lab results found. Upload a lab report to automatically extract and trend biomarker values.
                    </p>
                    <Link
                      href="/documents/upload"
                      className="mt-2 inline-flex items-center gap-1.5 text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                    >
                      <Upload className="size-3.5" />
                      Upload lab report
                    </Link>
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
