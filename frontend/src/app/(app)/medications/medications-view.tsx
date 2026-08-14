"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Copy,
  Info,
  Pill,
  RefreshCw,
  ShieldAlert,
  Scale,
  Upload,
  type LucideIcon,
} from "lucide-react";

import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { FlagChip } from "@/components/flag-chip";
import { Button } from "@/components/ui/button";
import { api, toErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { CrossCheckIssue, Medication, MedicationFlagKind } from "@/lib/types";

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

const SUMMARY_LABELS: Record<MedicationFlagKind, string> = {
  interaction: "Drug interactions",
  allergy: "Allergy contradictions",
  duplicate: "Duplicate prescriptions",
  dosage: "Dosage conflicts",
};

export function MedicationsView() {
  const [filter, setFilter] = useState("all");
  const [medications, setMedications] = useState<Medication[]>([]);
  const [crossChecks, setCrossChecks] = useState<CrossCheckIssue[]>([]);
  const [loading, setLoading] = useState(true);
  const [rerunning, setRerunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function loadData() {
    setLoading(true);
    setError(null);
    Promise.all([
      api().listMedications(),
      api().listCrossCheckIssues(),
    ])
      .then(([meds, issues]) => {
        setMedications(meds || []);
        setCrossChecks(issues || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(toErrorMessage(err));
        setLoading(false);
      });
  }

  useEffect(() => {
    loadData();
  }, []);

  const rows = useMemo(
    () =>
      medications.filter((medication) => {
        if (filter === "all") return true;
        if (filter === "flagged") return medication.flags.length > 0;
        return medication.status === filter;
      }),
    [medications, filter]
  );

  async function handleRerun() {
    setRerunning(true);
    setError(null);
    try {
      const issues = await api().listCrossCheckIssues();
      setCrossChecks(issues || []);
    } catch (caught) {
      setError(toErrorMessage(caught));
    } finally {
      setRerunning(false);
    }
  }

  const kinds: MedicationFlagKind[] = [
    "interaction",
    "allergy",
    "duplicate",
    "dosage",
  ];

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
          className="rounded-md border border-risk-high-border bg-risk-high-bg px-3.5 py-2.5 text-[13px] leading-[19px] text-risk-high"
        >
          {error}
        </p>
      )}

      {/* summary-row (26:599) */}
      <div className="grid w-full grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        {kinds.map((kind) => {
          const count = crossChecks.filter((i) => i.kind === kind).length;
          const high = kind === "allergy" || kind === "duplicate";
          const Icon = SUMMARY_ICONS[kind];
          return (
            <div
              key={kind}
              className="flex items-center gap-3.5 rounded-xl border border-neutral-200 bg-neutral-0 p-3.5 shadow-card"
            >
              <span
                className={cn(
                  "flex size-10 shrink-0 items-center justify-center rounded-lg",
                  count === 0
                    ? "bg-neutral-100"
                    : high
                      ? "bg-risk-high-bg"
                      : "bg-risk-med-bg"
                )}
              >
                <Icon
                  className={cn(
                    "size-[18px]",
                    count === 0
                      ? "text-neutral-500"
                      : high
                        ? "text-risk-high"
                        : "text-risk-med"
                  )}
                  strokeWidth={1.8}
                />
              </span>
              <div className="flex flex-col gap-0.5">
                <span className="text-lg leading-[26px] font-semibold tracking-[-0.2px] text-neutral-900">
                  {count}
                </span>
                <span className="type-overline text-neutral-500">
                  {SUMMARY_LABELS[kind]}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* medications-table (26:659) */}
      <div className="w-full overflow-hidden rounded-xl border border-neutral-200 bg-neutral-0 shadow-card">
        <div className="w-full overflow-x-auto">
          <table className="w-full min-w-[960px] border-collapse text-left">
            <thead>
              <tr className="bg-neutral-50">
                <th className="type-overline px-[18px] py-3 text-neutral-500">
                  MEDICATION
                </th>
                <th className="type-overline w-[140px] px-0 py-3 text-neutral-500">
                  DOSAGE
                </th>
                <th className="type-overline w-[140px] px-0 py-3 text-neutral-500">
                  FREQUENCY
                </th>
                <th className="type-overline w-[170px] px-0 py-3 text-neutral-500">
                  PRESCRIBER
                </th>
                <th className="type-overline w-[130px] px-0 py-3 text-neutral-500">
                  PRESCRIBED
                </th>
                <th className="type-overline w-[190px] px-0 py-3 text-neutral-500">
                  SAFETY FLAGS
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((medication) => (
                <tr
                  key={medication.id}
                  className="border-t border-neutral-200 transition-colors hover:bg-neutral-50"
                >
                  <td className="px-[18px] py-[13px]">
                    <div className="flex items-center gap-3">
                      <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-brand-50">
                        <Pill className="size-[15px] text-brand-700" strokeWidth={1.8} />
                      </span>
                      <span className="flex flex-col gap-0.5">
                        <span className="text-[13px] leading-[18px] font-medium text-neutral-800">
                          {medication.name}
                        </span>
                        <span className="text-xs leading-4 font-medium text-neutral-500">
                          {medication.genericName}
                        </span>
                      </span>
                    </div>
                  </td>
                  <td className="py-[13px] text-[13px] leading-[19px] text-neutral-600">
                    {medication.dosage}
                  </td>
                  <td className="py-[13px] text-[13px] leading-[19px] text-neutral-600">
                    {medication.frequency}
                  </td>
                  <td className="py-[13px] text-[13px] leading-[19px] text-neutral-600">
                    {medication.prescribedBy}
                  </td>
                  <td className="py-[13px] text-[13px] leading-[19px] text-neutral-500">
                    {medication.prescribedDate}
                  </td>
                  <td className="py-[13px] pr-[18px]">
                    <div className="flex flex-wrap gap-1.5">
                      {medication.flags.map((flag) => (
                        <FlagChip key={flag} kind={flag} />
                      ))}
                      {medication.flags.length === 0 && (
                        <span className="type-overline rounded-full bg-status-ok-bg px-2 py-0.5 text-status-ok">
                          NO CONFLICTS
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}

              {!loading && rows.length === 0 && (
                <tr className="border-t border-neutral-200">
                  <td colSpan={6} className="px-[18px] py-12 text-center">
                    <p className="text-sm leading-[21px] text-neutral-600">
                      No medication records found. Medications will appear here once extracted from your uploaded medical records.
                    </p>
                    <Link
                      href="/documents/upload"
                      className="mt-2 inline-flex items-center gap-1.5 text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                    >
                      <Upload className="size-3.5" />
                      Upload prescriptions or notes
                    </Link>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* note (26:802) */}
      <div className="flex w-full items-start gap-2.5 rounded-[10px] bg-neutral-50 px-4 py-3">
        <Info className="size-4 shrink-0 text-neutral-500" strokeWidth={1.8} />
        <p className="flex-1 text-[13px] leading-[19px] text-neutral-600">
          Cross-checks compare prescriptions across all your uploaded documents.
          Potential interactions and duplicate therapies are flagged for review with
          your doctor or pharmacist.
        </p>
      </div>
    </div>
  );
}
