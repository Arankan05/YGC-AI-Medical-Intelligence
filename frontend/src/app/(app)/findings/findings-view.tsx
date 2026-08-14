"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Filter, Sparkles, Upload } from "lucide-react";

import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { RiskBadge } from "@/components/risk-badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Finding, RiskLevel } from "@/lib/types";

const CHIPS: FilterChip[] = [
  { value: "all", label: "All findings" },
  { value: "high", label: "High risk" },
  { value: "medium", label: "Medium risk" },
  { value: "low", label: "Low risk" },
];

export function FindingsView() {
  const [filter, setFilter] = useState("all");
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    api()
      .listFindings()
      .then((data) => {
        if (active) {
          setFindings(data || []);
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
      findings.filter((finding) => {
        if (filter === "all") return true;
        return finding.risk === filter;
      }),
    [findings, filter]
  );

  return (
    <div className="flex w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
      {/* toolbar */}
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <FilterChips
          label="Filter findings by risk"
          chips={CHIPS}
          value={filter}
          onChange={setFilter}
        />
        <div className="flex items-center gap-2 text-xs leading-4 font-medium text-neutral-500">
          <Sparkles className="size-3.5 text-brand-700" strokeWidth={1.8} />
          <span>Cross-document contradiction engine</span>
        </div>
      </div>

      {/* findings list */}
      <div className="flex flex-col gap-3.5">
        {rows.map((finding) => (
          <div
            key={finding.id}
            className="flex w-full flex-col gap-3 rounded-xl border border-neutral-200 bg-neutral-0 p-4 shadow-card"
          >
            <div className="flex w-full flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <RiskBadge risk={finding.risk} />
                <h3 className="text-sm font-semibold text-neutral-900">
                  {finding.title}
                </h3>
              </div>
              <span className="text-xs text-neutral-500">{finding.detectedOn}</span>
            </div>
            <p className="text-sm text-neutral-600">{finding.summary}</p>
            <div className="flex justify-end">
              <Link
                href={`/findings/${finding.id}`}
                className="text-[13px] font-medium text-brand-700 hover:underline"
              >
                View evidence &nbsp;→
              </Link>
            </div>
          </div>
        ))}

        {!loading && rows.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-neutral-200 bg-neutral-0 py-16 text-center shadow-card">
            <p className="text-sm leading-5 text-neutral-600">
              No findings detected. Contradictions and safety conflicts will be flagged here as multiple medical records are uploaded.
            </p>
            <Link
              href="/documents/upload"
              className="inline-flex items-center gap-1.5 text-[13px] font-medium text-brand-700 hover:underline"
            >
              <Upload className="size-3.5" />
              Upload medical documents
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
