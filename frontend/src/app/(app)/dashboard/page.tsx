import type { Metadata } from "next";
import Link from "next/link";
import {
  AlertTriangle,
  Check,
  Pill,
  Sparkles,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { LabTrendChart } from "@/components/lab-trend-chart";
import { MetricCard } from "@/components/metric-card";
import { Panel, PanelHeader } from "@/components/panel";
import { RiskBadge } from "@/components/risk-badge";
import { FLAG_META } from "@/components/flag-chip";
import {
  dashboardMetrics,
  findings,
  haemoglobinTrend,
  medications,
  recentActivity,
} from "@/lib/data";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Dashboard — MediGuardian AI",
};

const ACTIVITY_STYLES: Record<
  (typeof recentActivity)[number]["tone"],
  { slot: string; ink: string; icon: LucideIcon }
> = {
  risk: {
    slot: "bg-risk-high-bg",
    ink: "text-risk-high",
    icon: AlertTriangle,
  },
  ok: { slot: "bg-status-ok-bg", ink: "text-status-ok", icon: Check },
  warn: { slot: "bg-risk-med-bg", ink: "text-risk-med", icon: TrendingUp },
};

/** Figma: 07 · Dashboard (node 19:63). */
export default function DashboardPage() {
  const priorityFindings = findings.slice(0, 2);
  const activeMedications = medications
    .filter((medication) => medication.status === "active")
    .slice(0, 5);
  const latest = haemoglobinTrend.points.at(-1);
  const outOfRange = Boolean(
    latest && latest.value < haemoglobinTrend.referenceLow
  );

  return (
    <AppShell title="Dashboard" subtitle="Overview of your medical records">
      <div className="flex min-h-full w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
        {/* metric-row (19:156) */}
        <div className="grid w-full grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {dashboardMetrics.map((metric) => (
            <MetricCard key={metric.id} metric={metric} />
          ))}
        </div>

        {/* columns (20:130) */}
        <div className="flex w-full flex-1 flex-col gap-4 xl:flex-row xl:items-stretch">
          <div className="flex w-full min-w-0 flex-1 flex-col gap-4">
            {/* panel · Priority AI findings (20:133) */}
            <Panel>
              <PanelHeader
                title="Priority AI findings"
                actions={
                  <Link
                    href="/findings"
                    className="text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                  >
                    View all {findings.length}
                  </Link>
                }
              />
              <div className="flex flex-col gap-3 px-[18px] py-4">
                {priorityFindings.map((finding) => {
                  const high = finding.risk === "high";
                  return (
                    <div
                      key={finding.id}
                      className={cn(
                        "flex w-full flex-col gap-[9px] rounded-[10px] border px-3.5 py-[13px]",
                        high
                          ? "border-risk-high-border bg-risk-high-bg"
                          : "border-neutral-200 bg-neutral-0"
                      )}
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
                      <div className="flex w-full flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2.5">
                          <span className="text-xs leading-4 font-medium text-neutral-500">
                            Confidence
                          </span>
                          <span className="h-1.5 w-[120px] overflow-hidden rounded-full bg-neutral-200">
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
                        </div>
                        <Link
                          href={`/findings/${finding.id}`}
                          className="text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                        >
                          View evidence &nbsp;→
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Panel>

            {/* panel · Haemoglobin trend (20:171) */}
            <Panel className="flex-1">
              <PanelHeader
                title={haemoglobinTrend.title}
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
                <LabTrendChart
                  points={haemoglobinTrend.points}
                  referenceLow={haemoglobinTrend.referenceLow}
                  referenceHigh={haemoglobinTrend.referenceHigh}
                  outOfRange={outOfRange}
                />
                <div className="flex w-full items-start justify-between gap-3">
                  {haemoglobinTrend.points.map((point, index) => {
                    // Only the latest reading is called out in colour.
                    const below =
                      index === haemoglobinTrend.points.length - 1 &&
                      point.value < haemoglobinTrend.referenceLow;
                    return (
                      <div
                        key={point.date}
                        className={cn(
                          "flex flex-col gap-0.5",
                          index === 1 && "items-center",
                          index === haemoglobinTrend.points.length - 1 &&
                            "items-end"
                        )}
                      >
                        <span className="text-xs leading-4 font-medium text-neutral-500">
                          {point.date}
                        </span>
                        <span
                          className={cn(
                            "text-[13px] leading-[18px] font-medium",
                            below ? "text-risk-high" : "text-neutral-800"
                          )}
                        >
                          {point.value} {haemoglobinTrend.unit}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="flex w-full items-start gap-2.5 rounded-[10px] bg-neutral-50 px-3.5 py-3">
                  <Sparkles
                    className="size-[17px] shrink-0 text-brand-700"
                    strokeWidth={1.8}
                  />
                  <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
                    <p className="text-xs leading-4 font-semibold text-neutral-700">
                      {haemoglobinTrend.referenceLabel}
                    </p>
                    <p className="text-[13px] leading-[19px] text-neutral-600">
                      {haemoglobinTrend.explanation}
                    </p>
                  </div>
                </div>
              </div>
            </Panel>
          </div>

          <div className="flex w-full flex-col gap-4 xl:w-[340px] xl:shrink-0">
            {/* panel · Recent activity (21:134) */}
            <Panel className="flex-1">
              <PanelHeader title="Recent activity" />
              <div className="flex flex-col gap-[13px] px-4 py-3.5">
                {recentActivity.map((item) => {
                  const style = ACTIVITY_STYLES[item.tone];
                  const Icon = style.icon;
                  return (
                    <div key={item.id} className="flex w-full items-start gap-[11px]">
                      <span
                        className={cn(
                          "flex size-[30px] shrink-0 items-center justify-center rounded-md",
                          style.slot
                        )}
                      >
                        <Icon
                          className={cn("size-[15px]", style.ink)}
                          strokeWidth={1.8}
                        />
                      </span>
                      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                        <span className="text-[13px] leading-[18px] font-medium text-neutral-800">
                          {item.title}
                        </span>
                        <span className="text-xs leading-4 font-medium text-neutral-500">
                          {item.meta}
                        </span>
                      </span>
                    </div>
                  );
                })}
              </div>
            </Panel>

            {/* panel · Active medications (21:177) */}
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
                {activeMedications.map((medication) => {
                  const flag = medication.flags[0];
                  const meta = flag ? FLAG_META[flag] : undefined;
                  const high = meta?.risk === "high";
                  return (
                    <div
                      key={medication.id}
                      className="flex w-full items-center gap-[11px]"
                    >
                      <span
                        className={cn(
                          "flex size-[30px] shrink-0 items-center justify-center rounded-md",
                          !meta
                            ? "bg-brand-50"
                            : high
                              ? "bg-risk-high-bg"
                              : "bg-risk-med-bg"
                        )}
                      >
                        <Pill
                          className={cn(
                            "size-[15px]",
                            !meta
                              ? "text-brand-700"
                              : high
                                ? "text-risk-high"
                                : "text-risk-med"
                          )}
                          strokeWidth={1.8}
                        />
                      </span>
                      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                        <span className="truncate text-[13px] leading-[18px] font-medium text-neutral-800">
                          {medication.name}
                        </span>
                        <span className="truncate text-xs leading-4 font-medium text-neutral-500">
                          {medication.dosage} · {medication.frequency.toLowerCase()}
                        </span>
                      </span>
                      {meta && (
                        <span
                          className={cn(
                            "type-overline shrink-0 rounded-full px-2 py-[3px]",
                            high
                              ? "bg-risk-high-bg text-risk-high"
                              : "bg-risk-med-bg text-risk-med"
                          )}
                        >
                          {meta.risk === "high" && flag === "allergy"
                            ? "Allergy"
                            : meta.label}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </Panel>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
