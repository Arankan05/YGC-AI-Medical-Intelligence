"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  FileText,
  Pill,
  ShieldAlert,
  Sparkles,
  Upload,
} from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { Panel, PanelHeader } from "@/components/panel";
import { RiskBadge } from "@/components/risk-badge";
import { api } from "@/lib/api";
import type {
  AllergyRecord,
  DashboardMetric,
  Finding,
  LabResult,
  MedicalDocument,
  MedicalOverview,
  Medication,
  TimelineEvent,
} from "@/lib/types";

export default function DashboardPage() {
  const [overview, setOverview] = useState<MedicalOverview | null>(null);
  const [documents, setDocuments] = useState<MedicalDocument[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [medications, setMedications] = useState<Medication[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [allergies, setAllergies] = useState<AllergyRecord[]>([]);
  const [labs, setLabs] = useState<LabResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.all([
      api().getOverview().catch(() => null),
      api().listDocuments().catch(() => []),
      api().listFindings().catch(() => []),
      api().listMedications().catch(() => []),
      api().listTimeline().catch(() => []),
      api().listAllergies().catch(() => []),
      api().listLabResults().catch(() => []),
    ])
      .then(([ov, docs, fnds, meds, tm, al, lb]) => {
        if (active) {
          setOverview(ov);
          setDocuments(docs || []);
          setFindings(fnds || (ov?.priorityFindings ?? []));
          setMedications(meds || (ov?.activeMedications ?? []));
          setTimeline(tm || (ov?.recentEvents ?? []));
          setAllergies(al || []);
          setLabs(lb || []);
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

  const totalDocs = overview?.totalDocuments ?? documents.length;
  const totalEvents = overview?.totalEvents ?? timeline.length;
  const totalMeds = overview?.totalMedications ?? medications.length;
  const totalFindings = overview?.totalFindings ?? findings.length;
  const priorityCount = findings.filter((f) => f.risk === "high" || f.risk === "medium").length;

  const metrics: DashboardMetric[] = [
    {
      id: "documents",
      kind: "documents",
      label: "MEDICAL DOCUMENTS",
      value: String(totalDocs),
      delta: totalDocs === 0 ? "Nothing uploaded" : `${totalDocs} uploaded`,
    },
    {
      id: "events",
      kind: "events",
      label: "MEDICAL EVENTS",
      value: String(totalEvents),
      delta: totalEvents === 0 ? "Nothing extracted" : `${totalEvents} events`,
    },
    {
      id: "medications",
      kind: "medications",
      label: "ACTIVE MEDICATIONS",
      value: String(totalMeds),
      delta: totalMeds === 0 ? "Nothing to check" : `${totalMeds} active`,
    },
    {
      id: "findings",
      kind: "findings",
      label: "AI FINDINGS",
      value: String(totalFindings),
      delta: totalFindings === 0 ? "Nothing analysed" : `${totalFindings} findings`,
    },
    {
      id: "priority",
      kind: "priority",
      label: "PRIORITY ITEMS",
      value: String(priorityCount),
      delta: priorityCount === 0 ? "Nothing flagged" : `${priorityCount} high/medium`,
    },
  ];

  return (
    <AppShell title="Dashboard" subtitle="Overview of your medical records">
      <div className="flex min-h-full w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
        {/* Metric Row */}
        <div className="grid w-full grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {metrics.map((metric) => (
            <MetricCard key={metric.id} metric={metric} muted={loading || totalDocs === 0} />
          ))}
        </div>

        {/* AI Medical Summary Banner */}
        {overview?.latestSummary && (
          <div className="flex w-full flex-col gap-2.5 rounded-xl border border-brand-200 bg-brand-50/70 p-4 shadow-sm">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Sparkles className="size-4 text-brand-700" />
                <h3 className="text-sm font-semibold text-brand-900">AI-Extracted Clinical Summary</h3>
              </div>
              {overview.confidenceScore !== undefined && (
                <span className="rounded-full bg-brand-100 px-2.5 py-0.5 text-xs font-semibold text-brand-800">
                  Confidence: {Math.round(overview.confidenceScore <= 1 ? overview.confidenceScore * 100 : overview.confidenceScore)}%
                </span>
              )}
            </div>
            <p className="text-[13px] leading-[21px] text-neutral-800">
              {overview.latestSummary}
            </p>
            <p className="text-[11px] text-neutral-500 italic">
              AI-assisted analysis · Please verify all medical information with a qualified healthcare professional.
            </p>
          </div>
        )}

        {/* Main 2-Column Clinical Layout */}
        <div className="flex w-full flex-1 flex-col gap-4 xl:flex-row xl:items-stretch">
          {/* Left Column: Priority Findings, Allergies Alert, and Lab Results */}
          <div className="flex w-full min-w-0 flex-1 flex-col gap-4">
            {/* Priority AI Findings */}
            <Panel>
              <PanelHeader
                title="Priority AI findings"
                actions={
                  findings.length > 0 ? (
                    <Link
                      href="/findings"
                      className="text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                    >
                      View all {findings.length}
                    </Link>
                  ) : undefined
                }
              />
              <div className="flex flex-col gap-3 px-[18px] py-4">
                {findings.length === 0 ? (
                  <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
                    <p className="text-sm leading-5 text-neutral-600">
                      No AI findings detected yet. Upload medical documents to begin contradiction analysis.
                    </p>
                    <Link
                      href="/documents/upload"
                      className="inline-flex items-center gap-1.5 text-[13px] font-medium text-brand-700 hover:underline"
                    >
                      <Upload className="size-3.5" />
                      Upload your first documents
                    </Link>
                  </div>
                ) : (
                  findings.slice(0, 3).map((finding) => (
                    <div
                      key={finding.id}
                      className="flex w-full flex-col gap-[9px] rounded-[10px] border border-neutral-200 bg-neutral-0 px-3.5 py-[13px]"
                    >
                      <div className="flex w-full flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2.5">
                          <RiskBadge risk={finding.risk} />
                          <p className="text-sm leading-5 font-medium text-neutral-900">
                            {finding.title}
                          </p>
                        </div>
                        <span className="text-xs leading-4 font-medium text-sidebar-ink-muted">
                          {finding.detectedOn}
                        </span>
                      </div>
                      <p className="text-[13px] leading-[19px] text-neutral-600">
                        {finding.summary}
                      </p>
                      <div className="flex w-full justify-end">
                        <Link
                          href={`/findings/${finding.id}`}
                          className="text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                        >
                          View evidence &nbsp;→
                        </Link>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Panel>

            {/* Known Allergies Alert Panel if available */}
            {allergies.length > 0 && (
              <Panel>
                <PanelHeader
                  title="Recorded Drug Allergies"
                  actions={
                    <Link
                      href="/allergies"
                      className="text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                    >
                      All allergies ({allergies.length})
                    </Link>
                  }
                />
                <div className="flex flex-col divide-y divide-neutral-100 px-4 py-2">
                  {allergies.slice(0, 3).map((al) => (
                    <div key={al.id} className="flex items-center justify-between py-2.5">
                      <div className="flex items-center gap-2.5">
                        <span className="flex size-7 shrink-0 items-center justify-center rounded bg-risk-high-bg text-risk-high">
                          <ShieldAlert className="size-3.5" />
                        </span>
                        <div className="flex flex-col">
                          <span className="text-[13px] font-semibold text-neutral-900">{al.medicationName}</span>
                          <span className="text-xs text-neutral-500">{al.reaction || "Reported reaction"}</span>
                        </div>
                      </div>
                      <span className="type-overline rounded-full bg-risk-high-bg px-2 py-0.5 text-risk-high">
                        {al.severity || "Moderate"}
                      </span>
                    </div>
                  ))}
                </div>
              </Panel>
            )}

            {/* Lab results & biomarker trends */}
            <Panel className="flex-1">
              <PanelHeader
                title="Lab results & biomarker trends"
                actions={
                  <Link
                    href="/lab-results"
                    className="text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                  >
                    Open lab results ({labs.length})
                  </Link>
                }
              />
              <div className="flex flex-col gap-3 px-[18px] py-4">
                {labs.length === 0 ? (
                  <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
                    <p className="text-sm leading-5 text-neutral-600">
                      No lab trends available yet. Lab results will be trended across time as reports are uploaded.
                    </p>
                    <Link
                      href="/documents/upload"
                      className="inline-flex items-center gap-1.5 text-[13px] font-medium text-brand-700 hover:underline"
                    >
                      <Upload className="size-3.5" />
                      Upload lab report
                    </Link>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                    {labs.slice(0, 4).map((lab) => (
                      <div
                        key={lab.id}
                        className="flex flex-col gap-1 rounded-lg border border-neutral-200 bg-neutral-50 p-3"
                      >
                        <div className="flex items-center justify-between gap-1">
                          <span className="text-xs font-semibold text-neutral-900 truncate">{lab.name}</span>
                          <span className="text-[11px] text-neutral-500">{lab.latestDate}</span>
                        </div>
                        <div className="flex items-baseline gap-1.5">
                          <span className="text-base font-bold text-neutral-900">
                            {lab.latestValueLabel || lab.latestValue}
                          </span>
                          <span className="text-xs text-neutral-500">{lab.unit}</span>
                        </div>
                        {lab.referenceRange && (
                          <span className="text-[11px] text-neutral-500">Ref: {lab.referenceRange}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Panel>
          </div>

          {/* Right Column: Recent Activity & Active Medications */}
          <div className="flex w-full flex-col gap-4 xl:w-[340px] xl:shrink-0">
            {/* Recent activity & Timeline */}
            <Panel className="flex-1">
              <PanelHeader
                title="Recent activity & events"
                actions={
                  <Link
                    href="/timeline"
                    className="text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                  >
                    Timeline ({timeline.length})
                  </Link>
                }
              />
              <div className="flex flex-col gap-[13px] px-4 py-3.5">
                {documents.length === 0 && timeline.length === 0 ? (
                  <p className="py-6 text-center text-[13px] leading-[19px] text-neutral-500">
                    No recent activity recorded yet.
                  </p>
                ) : (
                  documents.slice(0, 4).map((doc) => (
                    <Link
                      key={doc.id}
                      href={`/documents/${doc.id}`}
                      className="group flex w-full items-start gap-[11px] transition-colors hover:opacity-80"
                    >
                      <span className="flex size-[30px] shrink-0 items-center justify-center rounded-md bg-brand-50">
                        <FileText className="size-[15px] text-brand-700" strokeWidth={1.8} />
                      </span>
                      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                        <span className="truncate text-[13px] leading-[18px] font-medium text-neutral-800 group-hover:text-brand-700 group-hover:underline">
                          {doc.title}
                        </span>
                        <span className="text-xs leading-4 font-medium text-neutral-500">
                          {doc.type} · {doc.uploadedAt}
                        </span>
                      </span>
                    </Link>
                  ))
                )}
              </div>
            </Panel>

            {/* Active medications */}
            <Panel>
              <PanelHeader
                title="Active medications"
                actions={
                  <Link
                    href="/medications"
                    className="text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                  >
                    Manage ({medications.length})
                  </Link>
                }
              />
              <div className="flex flex-col gap-[11px] px-4 py-3.5">
                {medications.length === 0 ? (
                  <p className="py-6 text-center text-[13px] leading-[19px] text-neutral-500">
                    No active medications recorded yet.
                  </p>
                ) : (
                  medications.slice(0, 5).map((med) => (
                    <div key={med.id} className="flex w-full items-center gap-[11px]">
                      <span className="flex size-[30px] shrink-0 items-center justify-center rounded-md bg-brand-50">
                        <Pill className="size-[15px] text-brand-700" strokeWidth={1.8} />
                      </span>
                      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                        <span className="truncate text-[13px] leading-[18px] font-medium text-neutral-800">
                          {med.name}
                        </span>
                        <span className="truncate text-xs leading-4 font-medium text-neutral-500">
                          {med.dosage} · {med.frequency}
                        </span>
                      </span>
                    </div>
                  ))
                )}
              </div>
            </Panel>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
