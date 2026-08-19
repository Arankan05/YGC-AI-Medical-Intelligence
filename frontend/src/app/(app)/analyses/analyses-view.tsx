"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Brain,
  Info,
  Loader2,
  MessageSquare,
  Sparkles,
  Upload,
} from "lucide-react";

import { Panel } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { api, toErrorMessage } from "@/lib/api";
import type {
  AIAnalysisRecord,
  DocumentExtractionResultPayload,
  QAResultPayload,
} from "@/lib/types";

function DocumentExtractionCard({ analysis }: { analysis: AIAnalysisRecord }) {
  const rawResult = (analysis.result || {}) as DocumentExtractionResultPayload;
  const summary =
    typeof rawResult.summary === "string"
      ? rawResult.summary
      : analysis.summary;
  const docType =
    typeof rawResult.document_type_detected === "string"
      ? rawResult.document_type_detected
      : null;

  const counts = rawResult.persisted_counts || {};
  const medsCount = counts.prescriptions ?? counts.medications ?? 0;
  const findingsCount = counts.findings ?? 0;
  const labsCount = counts.lab_results ?? 0;
  const eventsCount = counts.events ?? 0;

  return (
    <Panel className="p-5">
      <div className="flex flex-col gap-3.5">
        {/* Top Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-neutral-200 pb-3">
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-brand-100 text-brand-700">
              <Sparkles className="size-4" strokeWidth={1.8} />
            </span>
            <div>
              <h3 className="text-sm font-semibold text-neutral-900">
                {analysis.analysisType.replace(/_/g, " ").toUpperCase()}
              </h3>
              {docType && (
                <span className="text-xs text-neutral-500">
                  Document Type: {docType.replace(/_/g, " ")}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {analysis.confidence !== undefined && (
              <span className="rounded-full bg-brand-50 border border-brand-200 px-2.5 py-0.5 text-xs font-semibold text-brand-700">
                {analysis.confidence}% Confidence
              </span>
            )}
            <span className="text-xs text-neutral-500">
              {analysis.createdAt}
            </span>
          </div>
        </div>

        {/* Summary */}
        {summary && (
          <div className="rounded-lg bg-neutral-50 p-3.5 text-[13px] leading-[20px] text-neutral-800">
            <span className="font-semibold text-neutral-900">
              Clinical Summary:{" "}
            </span>
            {summary}
          </div>
        )}

        {/* Extracted Entity Counts */}
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          <div className="flex flex-col rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2">
            <span className="type-overline text-neutral-500">
              MEDICATIONS
            </span>
            <span className="text-base font-semibold text-neutral-900">
              {medsCount}
            </span>
          </div>
          <div className="flex flex-col rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2">
            <span className="type-overline text-neutral-500">
              FINDINGS
            </span>
            <span className="text-base font-semibold text-neutral-900">
              {findingsCount}
            </span>
          </div>
          <div className="flex flex-col rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2">
            <span className="type-overline text-neutral-500">
              LAB TESTS
            </span>
            <span className="text-base font-semibold text-neutral-900">
              {labsCount}
            </span>
          </div>
          <div className="flex flex-col rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2">
            <span className="type-overline text-neutral-500">
              EVENTS
            </span>
            <span className="text-base font-semibold text-neutral-900">
              {eventsCount}
            </span>
          </div>
        </div>
      </div>
    </Panel>
  );
}

function QACard({ analysis }: { analysis: AIAnalysisRecord }) {
  const rawResult = (analysis.result || {}) as QAResultPayload;
  const paragraphs = Array.isArray(rawResult.paragraphs) ? rawResult.paragraphs : [];
  const citations = Array.isArray(rawResult.citations) ? rawResult.citations : [];
  const guidance = typeof rawResult.guidance === "string" ? rawResult.guidance : null;
  const refusal = rawResult.refusal;
  const cta = rawResult.cta;

  return (
    <Panel className="p-5">
      <div className="flex flex-col gap-3.5">
        {/* Top Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-neutral-200 pb-3">
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-brand-100 text-brand-700">
              <MessageSquare className="size-4" strokeWidth={1.8} />
            </span>
            <div>
              <h3 className="text-sm font-semibold text-neutral-900">
                MEDICAL QA
              </h3>
              <span className="text-xs text-neutral-500">
                Interactive Assistant Query
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {analysis.confidence !== undefined && (
              <span className="rounded-full bg-brand-50 border border-brand-200 px-2.5 py-0.5 text-xs font-semibold text-brand-700">
                {analysis.confidence}% Confidence
              </span>
            )}
            <span className="text-xs text-neutral-500">
              {analysis.createdAt}
            </span>
          </div>
        </div>

        {/* Refusal if present */}
        {refusal && (
          <div className="rounded-lg border border-risk-high-border bg-risk-high-bg p-3.5 text-[13px] leading-[20px] text-risk-high">
            <div className="font-semibold">{refusal.headline || refusal.overline || "Safety Notice"}</div>
            {refusal.suggestions && refusal.suggestions.length > 0 && (
              <ul className="mt-1.5 list-disc pl-5">
                {refusal.suggestions.map((s, idx) => (
                  <li key={idx}>{s}</li>
                ))}
              </ul>
            )}
            {refusal.footnote && <p className="mt-1 text-xs text-neutral-600">{refusal.footnote}</p>}
          </div>
        )}

        {/* Answer Paragraphs */}
        {paragraphs.length > 0 && (
          <div className="flex flex-col gap-2 rounded-lg bg-neutral-50 p-3.5 text-[13px] leading-[20px] text-neutral-800">
            {paragraphs.map((p, idx) => (
              <p key={idx}>{p}</p>
            ))}
          </div>
        )}

        {/* Guidance if present */}
        {guidance && (
          <div className="flex items-start gap-2 rounded-md border border-brand-100 bg-brand-50/50 p-3 text-xs text-brand-900">
            <Info className="mt-0.5 size-3.5 shrink-0 text-brand-600" />
            <p>{guidance}</p>
          </div>
        )}

        {/* Citations if present */}
        {citations.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <span className="type-overline text-neutral-500">CITATIONS ({citations.length})</span>
            <div className="flex flex-col gap-2">
              {citations.map((c, idx) => {
                const title = (c as unknown as Record<string, unknown>).document_title || c.documentTitle || "Source Document";
                const quote = c.quote || "";
                const page = c.page ? ` (p. ${c.page})` : "";
                return (
                  <div key={idx} className="rounded-md border border-neutral-200 bg-neutral-0 p-2.5 text-xs">
                    <span className="font-medium text-neutral-900">{String(title)}{page}: </span>
                    <span className="italic text-neutral-600">&ldquo;{quote}&rdquo;</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* CTA if present */}
        {cta && (
          <div className="flex items-center justify-between gap-2 rounded-md bg-neutral-100 p-3 text-xs">
            <span className="font-medium text-neutral-800">{cta.label}</span>
            {cta.note && <span className="text-neutral-500">{cta.note}</span>}
          </div>
        )}
      </div>
    </Panel>
  );
}

export function AnalysesView() {
  const [analyses, setAnalyses] = useState<AIAnalysisRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function loadAnalyses() {
    setLoading(true);
    setError(null);
    api()
      .listAnalyses()
      .then((data) => {
        setAnalyses(data || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(toErrorMessage(err));
        setLoading(false);
      });
  }

  useEffect(() => {
    loadAnalyses();
  }, []);

  return (
    <div className="flex w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
      {/* Header banner */}
      <div className="flex w-full flex-col gap-2.5 rounded-xl border border-brand-200 bg-brand-50/70 p-4 shadow-sm">
        <div className="flex items-center gap-2">
          <Brain className="size-4 text-brand-700" />
          <h3 className="text-sm font-semibold text-brand-900">
            AI Medical Intelligence Logs
          </h3>
        </div>
        <p className="text-[13px] leading-[20px] text-neutral-700">
          Records of clinical intelligence extraction and multi-document cross-checks performed by Google Gemini.
        </p>
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
            onClick={loadAnalyses}
            className="border-risk-high text-risk-high hover:bg-risk-high-bg"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Analyses List */}
      <div className="flex flex-col gap-4">
        {loading && (
          <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-neutral-200 bg-neutral-0 py-16 text-center shadow-card">
            <Loader2 className="size-5 animate-spin text-brand-600" />
            <p className="text-sm text-neutral-500">Loading AI analysis records...</p>
          </div>
        )}

        {!loading &&
          analyses.map((analysis) => {
            if (analysis.analysisType === "qa") {
              return <QACard key={analysis.id} analysis={analysis} />;
            }
            return <DocumentExtractionCard key={analysis.id} analysis={analysis} />;
          })}

        {!loading && analyses.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-neutral-200 bg-neutral-0 py-16 text-center shadow-card">
            <p className="text-sm leading-5 text-neutral-600">
              No AI analysis logs found. Upload and extract medical records to see AI reasoning logs here.
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

      {/* Safety notice */}
      <div className="flex w-full items-start gap-2.5 rounded-[10px] bg-neutral-50 px-4 py-3">
        <Info className="size-4 shrink-0 text-neutral-500" strokeWidth={1.8} />
        <p className="flex-1 text-[13px] leading-[19px] text-neutral-600">
          AI-assisted information is provided for informational purposes and should be verified with a qualified healthcare professional. Do not present AI analysis as a definitive medical diagnosis.
        </p>
      </div>
    </div>
  );
}
