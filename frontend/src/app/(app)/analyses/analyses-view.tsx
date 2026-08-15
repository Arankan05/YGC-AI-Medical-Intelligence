"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Brain,
  Info,
  Loader2,
  Sparkles,
  Upload,
} from "lucide-react";

import { Panel } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { api, toErrorMessage } from "@/lib/api";
import type { AIAnalysisRecord } from "@/lib/types";

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
            const rawResult = analysis.result || {};
            const summary =
              typeof rawResult.summary === "string"
                ? rawResult.summary
                : analysis.summary;
            const docType =
              typeof rawResult.document_type_detected === "string"
                ? rawResult.document_type_detected
                : null;
            const medsCount = Array.isArray(rawResult.medications)
              ? rawResult.medications.length
              : 0;
            const findingsCount = Array.isArray(rawResult.findings)
              ? rawResult.findings.length
              : 0;
            const labsCount = Array.isArray(rawResult.lab_results)
              ? rawResult.lab_results.length
              : 0;
            const eventsCount = Array.isArray(rawResult.events)
              ? rawResult.events.length
              : 0;

            return (
              <Panel key={analysis.id} className="p-5">
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
