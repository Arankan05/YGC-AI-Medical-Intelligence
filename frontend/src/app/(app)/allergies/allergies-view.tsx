"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Info, Loader2, ShieldAlert, Upload } from "lucide-react";

import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { Button } from "@/components/ui/button";
import { api, toErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { AllergyRecord } from "@/lib/types";

const CHIPS: FilterChip[] = [
  { value: "all", label: "All allergies" },
  { value: "severe", label: "Severe" },
  { value: "moderate", label: "Moderate" },
  { value: "mild", label: "Mild" },
];

function SeverityBadge({ severity }: { severity?: string }) {
  const s = (severity || "moderate").toLowerCase();
  let pillClass = "bg-risk-med-bg text-risk-med border-risk-med-border";
  let dotClass = "bg-risk-med";

  if (s.includes("severe") || s.includes("high")) {
    pillClass = "bg-risk-high-bg text-risk-high border-risk-high-border";
    dotClass = "bg-risk-high";
  } else if (s.includes("mild") || s.includes("low")) {
    pillClass = "bg-status-ok-bg text-status-ok border-status-ok-border";
    dotClass = "bg-status-ok";
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider",
        pillClass
      )}
    >
      <span className={cn("size-1.5 rounded-full", dotClass)} />
      {severity || "Moderate"}
    </span>
  );
}

export function AllergiesView() {
  const [filter, setFilter] = useState("all");
  const [allergies, setAllergies] = useState<AllergyRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function loadAllergies() {
    setLoading(true);
    setError(null);
    api()
      .listAllergies()
      .then((data) => {
        setAllergies(data || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(toErrorMessage(err));
        setLoading(false);
      });
  }

  useEffect(() => {
    loadAllergies();
  }, []);

  const rows = useMemo(
    () =>
      allergies.filter((item) => {
        if (filter === "all") return true;
        const s = (item.severity || "moderate").toLowerCase();
        return s.includes(filter);
      }),
    [allergies, filter]
  );

  return (
    <div className="flex w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
      {/* Toolbar */}
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <FilterChips
          label="Filter allergies by severity"
          chips={CHIPS}
          value={filter}
          onChange={setFilter}
        />
        <Button
          nativeButton={false}
          render={<Link href="/documents/upload" />}
          className="gap-2"
        >
          <Upload className="size-4" strokeWidth={1.8} />
          Upload documents
        </Button>
      </div>

      {error && (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 rounded-md border border-risk-high-border bg-risk-high-bg px-3.5 py-2.5 text-[13px] leading-[19px] text-risk-high"
        >
          <span>{error}</span>
          <Button
            size="sm"
            variant="outline"
            onClick={loadAllergies}
            className="border-risk-high text-risk-high hover:bg-risk-high-bg"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Allergies Table */}
      <div className="w-full overflow-hidden rounded-xl border border-neutral-200 bg-neutral-0 shadow-card">
        <div className="w-full overflow-x-auto">
          <table className="w-full min-w-[860px] border-collapse text-left">
            <thead>
              <tr className="bg-neutral-50">
                <th className="type-overline px-[18px] py-3 text-neutral-500">
                  ALLERGEN / SUBSTANCE
                </th>
                <th className="type-overline w-[160px] px-0 py-3 text-neutral-500">
                  NORMALIZED INGREDIENT
                </th>
                <th className="type-overline w-[220px] px-0 py-3 text-neutral-500">
                  REACTION / SYMPTOMS
                </th>
                <th className="type-overline w-[140px] px-0 py-3 text-neutral-500">
                  SEVERITY
                </th>
                <th className="type-overline w-[140px] px-3 py-3 text-right text-neutral-500">
                  RECORDED DATE
                </th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr className="border-t border-neutral-200">
                  <td colSpan={5} className="px-[18px] py-12 text-center text-neutral-500">
                    <div className="flex items-center justify-center gap-2 text-sm">
                      <Loader2 className="size-4 animate-spin text-brand-600" />
                      Loading allergy records...
                    </div>
                  </td>
                </tr>
              )}

              {!loading &&
                rows.map((allergy) => (
                  <tr
                    key={allergy.id}
                    className="border-t border-neutral-200 transition-colors hover:bg-neutral-50"
                  >
                    <td className="px-[18px] py-[13px]">
                      <div className="flex items-center gap-3">
                        <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-risk-high-bg text-risk-high">
                          <ShieldAlert className="size-[16px]" strokeWidth={1.8} />
                        </span>
                        <div className="flex flex-col gap-0.5">
                          <span className="text-[13px] leading-[18px] font-semibold text-neutral-900">
                            {allergy.medicationName}
                          </span>
                          {allergy.sourceDocumentName && (
                            <span className="text-xs text-neutral-500">
                              Source: {allergy.sourceDocumentName}
                            </span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="py-[13px] text-[13px] text-neutral-600">
                      {allergy.normalizedMedicationName || allergy.medicationName}
                    </td>
                    <td className="py-[13px] text-[13px] text-neutral-700">
                      {allergy.reaction || "Adverse clinical reaction reported"}
                    </td>
                    <td className="py-[13px]">
                      <SeverityBadge severity={allergy.severity} />
                    </td>
                    <td className="px-3 py-[13px] text-right text-[13px] text-neutral-500">
                      {allergy.recordedDate}
                    </td>
                  </tr>
                ))}

              {!loading && rows.length === 0 && (
                <tr className="border-t border-neutral-200">
                  <td colSpan={5} className="px-[18px] py-12 text-center">
                    <p className="text-sm leading-[21px] text-neutral-600">
                      {filter === "all"
                        ? "No known drug allergies recorded. Document extraction will automatically flag and track allergies from your records."
                        : "No allergies match this severity filter."}
                    </p>
                    <Link
                      href="/documents/upload"
                      className="mt-2 inline-flex items-center gap-1.5 text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                    >
                      <Upload className="size-3.5" />
                      Upload medical documents
                    </Link>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Safety notice */}
      <div className="flex w-full items-start gap-2.5 rounded-[10px] bg-neutral-50 px-4 py-3">
        <Info className="size-4 shrink-0 text-neutral-500" strokeWidth={1.8} />
        <p className="flex-1 text-[13px] leading-[19px] text-neutral-600">
          Allergy records are AI-extracted from your uploaded clinical documentation. Please always verify known drug allergies and adverse reaction risks with your prescribing physician and pharmacist.
        </p>
      </div>
    </div>
  );
}
