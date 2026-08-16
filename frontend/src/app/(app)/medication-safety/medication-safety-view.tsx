"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  Info,
  Loader2,
  Pill,
  RefreshCw,
  Scale,
  ShieldAlert,
  Upload,
  type LucideIcon,
} from "lucide-react";

import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { FLAG_META, FlagChip } from "@/components/flag-chip";
import { RiskBadge } from "@/components/risk-badge";
import { Button } from "@/components/ui/button";
import { api, toErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  MedicationFlagKind,
  MedicationSafetyReport,
  RiskLevel,
} from "@/lib/types";

const CHIPS: FilterChip[] = [
  { value: "all", label: "All issues" },
  { value: "high", label: "High risk" },
  { value: "medium", label: "Medium risk" },
  { value: "low", label: "Low risk" },
];

/** The four categories the safety engine reports, in reading order. */
const KINDS: MedicationFlagKind[] = [
  "allergy",
  "interaction",
  "duplicate",
  "dosage",
];

const SUMMARY_ICONS: Record<MedicationFlagKind, LucideIcon> = {
  allergy: ShieldAlert,
  interaction: AlertTriangle,
  duplicate: Copy,
  dosage: Scale,
};

const SUMMARY_LABELS: Record<MedicationFlagKind, string> = {
  allergy: "Allergy contradictions",
  interaction: "Drug interactions",
  duplicate: "Duplicate prescriptions",
  dosage: "Dosage conflicts",
};

/** Tile colouring uses the existing risk tokens — no new colours. */
const TILE_TONE: Record<RiskLevel, { bg: string; text: string }> = {
  high: { bg: "bg-risk-high-bg", text: "text-risk-high" },
  medium: { bg: "bg-risk-med-bg", text: "text-risk-med" },
  low: { bg: "bg-risk-low-bg", text: "text-risk-low" },
};

const RISK_ORDER: Record<RiskLevel, number> = { high: 0, medium: 1, low: 2 };

/**
 * Tone for a category tile: the highest risk actually detected in that
 * category, so a tile never understates what the cards below it show. Falls
 * back to the category's usual tone when nothing was detected.
 */
function toneForKind(kind: MedicationFlagKind, risks: RiskLevel[]): RiskLevel {
  if (risks.length === 0) return FLAG_META[kind].risk;
  return risks.reduce((worst, risk) =>
    RISK_ORDER[risk] < RISK_ORDER[worst] ? risk : worst
  );
}

export function MedicationSafetyView() {
  const [filter, setFilter] = useState("all");
  const [report, setReport] = useState<MedicationSafetyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [rerunning, setRerunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function loadReport() {
    setLoading(true);
    setError(null);
    api()
      .runMedicationSafetyCheck()
      .then((data) => {
        setReport(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(toErrorMessage(err));
        setLoading(false);
      });
  }

  useEffect(() => {
    loadReport();
  }, []);

  async function handleRerun() {
    setRerunning(true);
    setError(null);
    try {
      const data = await api().runMedicationSafetyCheck();
      setReport(data);
    } catch (caught) {
      setError(toErrorMessage(caught));
    } finally {
      setRerunning(false);
    }
  }

  const issues = useMemo(() => report?.issues ?? [], [report]);

  const rows = useMemo(
    () => issues.filter((issue) => filter === "all" || issue.risk === filter),
    [issues, filter]
  );

  const hasMedications = (report?.activeMedicationCount ?? 0) > 0;
  const showEmptyRecords = !loading && report !== null && !hasMedications;
  const showAllClear = !loading && report !== null && hasMedications && issues.length === 0;

  return (
    <div className="flex w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
      {/* toolbar */}
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <FilterChips
          label="Filter safety issues by risk"
          chips={CHIPS}
          value={filter}
          onChange={setFilter}
        />
        <Button
          onClick={handleRerun}
          disabled={rerunning || loading}
          aria-busy={rerunning}
          className="gap-2"
        >
          <RefreshCw
            className={cn("size-[15px]", rerunning && "animate-spin")}
            strokeWidth={1.8}
          />
          {rerunning ? "Re-running…" : "Re-run cross-check"}
        </Button>
      </div>

      {error && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-risk-high-border bg-risk-high-bg px-3.5 py-2.5 text-[13px] leading-[19px] text-risk-high"
        >
          <span>{error}</span>
          <Button
            size="sm"
            variant="outline"
            onClick={loadReport}
            className="border-risk-high text-risk-high hover:bg-risk-high-bg"
          >
            Retry
          </Button>
        </div>
      )}

      {/* report meta */}
      <p aria-live="polite" className="text-[13px] leading-[19px] text-neutral-500">
        {loading
          ? "Running medication safety checks…"
          : report
            ? `${report.activeMedicationCount} active ${
                report.activeMedicationCount === 1 ? "medication" : "medications"
              } checked · ${report.findingCount} ${
                report.findingCount === 1 ? "issue" : "issues"
              } detected · as of ${report.referenceDate}`
            : "Safety report unavailable."}
      </p>

      {/* summary-row */}
      <div className="grid w-full grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        {KINDS.map((kind) => {
          const matching = issues.filter((issue) => issue.kind === kind);
          const count = matching.length;
          const tone = TILE_TONE[toneForKind(kind, matching.map((i) => i.risk))];
          const Icon = SUMMARY_ICONS[kind];
          return (
            <div
              key={kind}
              className="flex items-center gap-3.5 rounded-xl border border-neutral-200 bg-neutral-0 p-3.5 shadow-card"
            >
              <span
                className={cn(
                  "flex size-10 shrink-0 items-center justify-center rounded-lg",
                  count === 0 ? "bg-neutral-100" : tone.bg
                )}
              >
                <Icon
                  className={cn(
                    "size-[18px]",
                    count === 0 ? "text-neutral-500" : tone.text
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

      {/* issues list */}
      <div className="flex flex-col gap-3.5">
        {loading && (
          <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-neutral-200 bg-neutral-0 py-16 text-center shadow-card">
            <Loader2 className="size-5 animate-spin text-brand-600" />
            <p className="text-sm text-neutral-500">
              Running medication safety checks...
            </p>
          </div>
        )}

        {!loading &&
          rows.map((issue) => {
            const confidencePct = Math.round(issue.confidence * 100);
            return (
              <article
                key={issue.id}
                className="flex w-full flex-col gap-3 rounded-xl border border-neutral-200 bg-neutral-0 p-4 shadow-card"
              >
                <div className="flex w-full flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <RiskBadge risk={issue.risk} />
                    <FlagChip flag={issue.kind} />
                  </div>
                  <span className="text-xs leading-4 text-neutral-500">
                    Confidence {confidencePct}%
                  </span>
                </div>

                <h3 className="text-sm leading-[20px] font-semibold text-neutral-900">
                  {issue.title}
                </h3>

                {issue.medications.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="type-overline text-neutral-500">
                      Medications involved
                    </span>
                    {issue.medications.map((medication) => (
                      <span
                        key={medication}
                        className="inline-flex items-center gap-1.5 rounded-full bg-neutral-100 px-2.5 py-[3px] text-xs leading-4 font-medium text-neutral-700"
                      >
                        <Pill className="size-3" strokeWidth={1.8} />
                        {medication}
                      </span>
                    ))}
                  </div>
                )}

                <p className="text-sm leading-[21px] text-neutral-600">
                  {issue.explanation}
                </p>

                {issue.recommendation && (
                  <div className="rounded-lg bg-neutral-50 p-2.5 text-xs leading-[18px] text-neutral-700">
                    <span className="font-semibold text-neutral-800">
                      Recommendation:{" "}
                    </span>
                    {issue.recommendation}
                  </div>
                )}
              </article>
            );
          })}

        {showAllClear && (
          <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-status-ok-border bg-status-ok-bg py-16 text-center">
            <CheckCircle2 className="size-6 text-status-ok" strokeWidth={1.8} />
            <p className="text-sm leading-5 font-semibold text-status-ok">
              No safety issues detected
            </p>
            <p className="max-w-[520px] text-[13px] leading-[19px] text-neutral-600">
              Your {report?.activeMedicationCount} active{" "}
              {report?.activeMedicationCount === 1 ? "medication was" : "medications were"}{" "}
              checked for allergy contradictions, drug interactions, duplicate therapy
              and dosage conflicts.
            </p>
          </div>
        )}

        {showEmptyRecords && (
          <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-neutral-200 bg-neutral-0 py-16 text-center shadow-card">
            <p className="max-w-[520px] text-sm leading-5 text-neutral-600">
              No active medications to check yet. Safety checks run automatically once
              prescriptions are extracted from your uploaded medical records.
            </p>
            <Link
              href="/documents/upload"
              className="inline-flex items-center gap-1.5 text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
            >
              <Upload className="size-3.5" />
              Upload prescriptions or notes
            </Link>
          </div>
        )}

        {!loading && issues.length > 0 && rows.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-neutral-200 bg-neutral-0 py-16 text-center shadow-card">
            <p className="text-sm leading-5 text-neutral-600">
              No safety issues match this risk filter.
            </p>
          </div>
        )}
      </div>

      {/* safety notice */}
      <div className="flex w-full items-start gap-2.5 rounded-[10px] bg-neutral-50 px-4 py-3">
        <Info className="size-4 shrink-0 text-neutral-500" strokeWidth={1.8} />
        <p className="flex-1 text-[13px] leading-[19px] text-neutral-600">
          Safety checks are rule-based and run against the medications extracted from
          your uploaded documents. They screen a limited set of known issues and are not
          a substitute for professional review — always confirm with your doctor or
          pharmacist before changing any medicine.
        </p>
      </div>
    </div>
  );
}
