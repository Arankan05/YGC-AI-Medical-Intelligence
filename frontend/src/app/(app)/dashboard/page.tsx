"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  FileText,
  Pill,
  Sparkles,
  TrendingUp,
  Upload,
} from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { Panel, PanelHeader } from "@/components/panel";
import { RiskBadge } from "@/components/risk-badge";
import { api } from "@/lib/api";
import { emptyStateMetrics } from "@/lib/data";
import { cn } from "@/lib/utils";
import type { DashboardMetric, Finding, MedicalDocument, Medication } from "@/lib/types";

export default function DashboardPage() {
  const [documents, setDocuments] = useState<MedicalDocument[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [medications, setMedications] = useState<Medication[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.all([
      api().listDocuments(),
      api().listFindings(),
      api().listMedications(),
    ])
      .then(([docs, fnds, meds]) => {
        if (active) {
          setDocuments(docs || []);
          setFindings(fnds || []);
          setMedications(meds || []);
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

  const metrics: DashboardMetric[] = [
    {
      id: "documents",
      kind: "documents",
      label: "MEDICAL DOCUMENTS",
      value: String(documents.length),
      delta: documents.length === 0 ? "Nothing uploaded" : `${documents.length} uploaded`,
    },
    {
      id: "events",
      kind: "events",
      label: "MEDICAL EVENTS",
      value: "0",
      delta: "Nothing extracted",
    },
    {
      id: "medications",
      kind: "medications",
      label: "ACTIVE MEDICATIONS",
      value: String(medications.length),
      delta: medications.length === 0 ? "Nothing to check" : `${medications.length} active`,
    },
    {
      id: "findings",
      kind: "findings",
      label: "AI FINDINGS",
      value: String(findings.length),
      delta: findings.length === 0 ? "Nothing analysed" : `${findings.length} findings`,
    },
    {
      id: "priority",
      kind: "priority",
      label: "PRIORITY ITEMS",
      value: "0",
      delta: "Nothing flagged",
    },
  ];

  return (
    <AppShell title="Dashboard" subtitle="Overview of your medical records">
      <div className="flex min-h-full w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
        {/* metric-row (19:156) */}
        <div className="grid w-full grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {metrics.map((metric) => (
            <MetricCard key={metric.id} metric={metric} muted={documents.length === 0} />
          ))}
        </div>

        {/* columns (20:130) */}
        <div className="flex w-full flex-1 flex-col gap-4 xl:flex-row xl:items-stretch">
          <div className="flex w-full min-w-0 flex-1 flex-col gap-4">
            {/* panel · Priority AI findings */}
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
                  findings.slice(0, 2).map((finding) => (
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

            {/* panel · Lab trend */}
            <Panel className="flex-1">
              <PanelHeader
                title="Lab results & biomarker trends"
                actions={
                  <Link
                    href="/lab-results"
                    className="text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                  >
                    Open lab results
                  </Link>
                }
              />
              <div className="flex flex-col gap-3 px-[18px] py-4">
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
              </div>
            </Panel>
          </div>

          <div className="flex w-full flex-col gap-4 xl:w-[340px] xl:shrink-0">
            {/* panel · Recent activity */}
            <Panel className="flex-1">
              <PanelHeader title="Recent activity" />
              <div className="flex flex-col gap-[13px] px-4 py-3.5">
                {documents.length === 0 ? (
                  <p className="py-6 text-center text-[13px] leading-[19px] text-neutral-500">
                    No recent activity recorded yet.
                  </p>
                ) : (
                  documents.slice(0, 5).map((doc) => (
                    <div key={doc.id} className="flex w-full items-start gap-[11px]">
                      <span className="flex size-[30px] shrink-0 items-center justify-center rounded-md bg-brand-50">
                        <FileText className="size-[15px] text-brand-700" strokeWidth={1.8} />
                      </span>
                      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                        <span className="truncate text-[13px] leading-[18px] font-medium text-neutral-800">
                          {doc.title}
                        </span>
                        <span className="text-xs leading-4 font-medium text-neutral-500">
                          Uploaded · {doc.uploadedAt}
                        </span>
                      </span>
                    </div>
                  ))
                )}
              </div>
            </Panel>

            {/* panel · Active medications */}
            <Panel>
              <PanelHeader
                title="Active medications"
                actions={
                  <Link
                    href="/medications"
                    className="text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                  >
                    Manage
                  </Link>
                }
              />
              <div className="flex flex-col gap-[11px] px-4 py-3.5">
                {medications.length === 0 ? (
                  <p className="py-6 text-center text-[13px] leading-[19px] text-neutral-500">
                    No active medications recorded yet.
                  </p>
                ) : (
                  medications.map((med) => (
                    <div key={med.id} className="flex w-full items-center gap-[11px]">
                      <span className="flex size-[30px] shrink-0 items-center justify-center rounded-md bg-brand-50">
                        <Pill className="size-[15px] text-brand-700" strokeWidth={1.8} />
                      </span>
                      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                        <span className="truncate text-[13px] leading-[18px] font-medium text-neutral-800">
                          {med.name}
                        </span>
                        <span className="truncate text-xs leading-4 font-medium text-neutral-500">
                          {med.dosage}
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
