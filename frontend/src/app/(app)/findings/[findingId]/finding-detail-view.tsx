"use client";

import Link from "next/link";
import { useState } from "react";
import { FileText, MapPin } from "lucide-react";

import { Panel, PanelHeader } from "@/components/panel";
import { RiskBadge } from "@/components/risk-badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Finding, RiskLevel } from "@/lib/types";

const RISK_SURFACE: Record<RiskLevel, string> = {
  high: "border-risk-high-border bg-risk-high-bg",
  medium: "border-risk-med-border bg-risk-med-bg",
  low: "border-risk-low-border bg-risk-low-bg",
};

const RISK_INK: Record<RiskLevel, string> = {
  high: "text-risk-high",
  medium: "text-risk-med",
  low: "text-risk-low",
};

const RISK_FILL: Record<RiskLevel, string> = {
  high: "bg-risk-high",
  medium: "bg-risk-med",
  low: "bg-risk-low",
};

const QUOTE_RULE: Record<RiskLevel, string> = {
  high: "border-l-risk-high",
  medium: "border-l-risk-med",
  low: "border-l-risk-low",
};

export function FindingDetailView({ finding }: { finding: Finding }) {
  const [reviewed, setReviewed] = useState(false);

  const facts = [
    { label: "CATEGORY", value: finding.categoryName },
    { label: "DETECTED", value: finding.detectedAt },
    { label: "DOCUMENTS INVOLVED", value: finding.documentsInvolved },
    { label: "CONFIDENCE", value: `${finding.confidence}%` },
    { label: "STATUS", value: reviewed ? "Reviewed by you" : finding.reviewStatus },
  ];

  return (
    <div className="flex min-h-full w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
      {/* finding-hero (29:849) */}
      <div
        className={cn(
          "flex w-full flex-col gap-2.5 rounded-xl border px-5 py-4",
          RISK_SURFACE[finding.risk]
        )}
      >
        <div className="flex w-full flex-wrap items-center gap-3">
          <RiskBadge risk={finding.risk} />
          <h2 className="text-[22px] leading-[30px] font-semibold tracking-[-0.3px] text-neutral-900">
            {finding.title}
          </h2>
        </div>
        <dl className="flex flex-wrap items-start gap-x-[22px] gap-y-3">
          {facts.map((fact) => (
            <div key={fact.label} className="flex flex-col gap-[3px]">
              <dt className="type-overline text-neutral-500">{fact.label}</dt>
              <dd className="text-[13px] leading-[18px] font-medium text-neutral-800">
                {fact.value}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      {/* columns (29:871) */}
      <div className="flex w-full flex-1 flex-col gap-4 xl:flex-row xl:items-stretch">
        <div className="flex w-full min-w-0 flex-1 flex-col gap-[13px]">
          <Panel>
            <PanelHeader title="What we found" className="py-[11px]" />
            <div className="px-[18px] py-3">
              <p className="text-sm leading-[21px] text-neutral-700">
                {finding.whatThisMeans}
              </p>
            </div>
          </Panel>

          <Panel>
            <PanelHeader
              title="Evidence"
              className="py-[11px]"
              actions={
                <Link
                  href="/documents"
                  className="text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                >
                  Open both documents
                </Link>
              }
            />
            <div className="flex flex-col gap-2.5 px-[18px] py-3">
              {finding.evidence.map((evidence) => (
                <div
                  key={evidence.id}
                  className="flex w-full flex-col gap-[9px] rounded-[10px] border border-neutral-200 bg-neutral-50 px-3.5 py-3"
                >
                  <div className="flex w-full items-center gap-2.5">
                    <FileText
                      className="size-[15px] shrink-0 text-brand-700"
                      strokeWidth={1.8}
                    />
                    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="truncate text-[13px] leading-[18px] font-medium text-neutral-800">
                        {evidence.documentTitle}
                      </span>
                      <span className="truncate text-xs leading-4 font-medium text-neutral-500">
                        Page {evidence.page} · {evidence.recordedOn}
                      </span>
                    </span>
                    <Link
                      href="/documents"
                      className="shrink-0 text-xs leading-4 font-semibold text-brand-700 hover:underline"
                    >
                      Open →
                    </Link>
                  </div>
                  <blockquote
                    className={cn(
                      "w-full rounded-lg border-l-[3px] bg-neutral-0 px-3 py-2.5 text-[13px] leading-[19px] text-neutral-700",
                      QUOTE_RULE[evidence.tone ?? finding.risk]
                    )}
                  >
                    {evidence.quote}
                  </blockquote>
                </div>
              ))}
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="How this was determined" className="py-[11px]" />
            <ol className="flex flex-col gap-2.5 px-[18px] py-3">
              {finding.determination.map((step, index) => {
                const ai = step.kind === "ai";
                return (
                  <li key={step.text} className="flex w-full items-start gap-3">
                    <span
                      className={cn(
                        "flex size-6 shrink-0 items-center justify-center rounded-full text-xs leading-4 font-semibold",
                        ai
                          ? "bg-brand-50 text-brand-800"
                          : "bg-neutral-100 text-neutral-600"
                      )}
                    >
                      {index + 1}
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
                      <span
                        className={cn(
                          "type-overline w-fit rounded-[5px] px-[7px] py-0.5",
                          ai
                            ? "bg-brand-50 text-brand-800"
                            : "bg-neutral-100 text-neutral-600"
                        )}
                      >
                        {ai ? "AI REASONING" : "DETERMINISTIC"}
                      </span>
                      <span className="text-[13px] leading-[19px] text-neutral-600">
                        {step.text}
                      </span>
                    </span>
                  </li>
                );
              })}
            </ol>
          </Panel>
        </div>

        <div className="flex w-full flex-col gap-[13px] xl:w-[360px] xl:shrink-0">
          <Panel>
            <PanelHeader title="Risk and confidence" className="py-[11px]" />
            <div className="flex flex-col gap-2.5 px-[18px] py-3">
              <div
                className={cn(
                  "flex w-full flex-col gap-[9px] rounded-[10px] px-3.5 py-[13px]",
                  RISK_SURFACE[finding.risk]
                )}
              >
                <div
                  className={cn(
                    "flex w-full items-baseline justify-between gap-3",
                    RISK_INK[finding.risk]
                  )}
                >
                  <p className="text-[22px] leading-[30px] font-semibold tracking-[-0.3px] uppercase">
                    {finding.risk}
                  </p>
                  <p className="text-[13px] leading-[18px] font-medium">
                    {finding.confidence}% confidence
                  </p>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-0">
                  <div
                    className={cn("h-2 rounded-full", RISK_FILL[finding.risk])}
                    style={{ width: `${finding.confidence}%` }}
                  />
                </div>
                <p className="text-[13px] leading-[19px] text-neutral-700">
                  {finding.guidance}. High-risk findings automatically unlock the
                  healthcare provider search.
                </p>
              </div>

              <p className="type-overline text-neutral-500">
                CONTRIBUTING FACTORS
              </p>
              {finding.contributingFactors.map((factor) => (
                <div key={factor} className="flex w-full items-start gap-2.5">
                  <span className="flex size-[18px] shrink-0 items-center justify-center rounded-[5px] bg-status-ok-bg text-xs leading-4 font-semibold text-status-ok">
                    +
                  </span>
                  <p className="flex-1 text-[13px] leading-[19px] text-neutral-600">
                    {factor}
                  </p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Recommended action" className="py-[11px]" />
            <div className="flex flex-col gap-2.5 px-[18px] py-3">
              <p className="text-[13px] leading-[19px] text-neutral-700">
                {finding.recommendedAction}
              </p>
              <div className="flex w-full flex-col gap-1.5 rounded-[10px] border border-brand-200 bg-brand-50 px-3.5 py-3">
                <p className="type-overline text-brand-800">
                  SUITABLE PROFESSIONAL
                </p>
                <p className="text-sm leading-5 font-medium text-neutral-900">
                  {finding.suitableProfessional.title}
                </p>
                <p className="text-[13px] leading-[19px] text-neutral-600">
                  {finding.suitableProfessional.rationale}
                </p>
              </div>
              <Button
                render={<Link href="/providers" />}
                className="w-full gap-[9px] py-3"
              >
                <MapPin className="size-4" strokeWidth={1.8} />
                Find healthcare providers nearby
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setReviewed((value) => !value)}
                className="w-full py-[11px]"
              >
                {reviewed ? "Reviewed — undo" : "Mark as reviewed"}
              </Button>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
