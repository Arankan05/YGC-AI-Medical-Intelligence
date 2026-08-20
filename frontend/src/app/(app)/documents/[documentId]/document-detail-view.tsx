"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  ArrowLeft,
  Beaker,
  FileText,
  Info,
  Loader2,
  Pill,
  ShieldAlert,
  Sparkles,
  Trash2,
} from "lucide-react";

import { StatusPill } from "@/components/status-pill";
import { Button } from "@/components/ui/button";
import { api, toErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { queryClient } from "@/lib/query-client";
import type { DocumentDetail } from "@/lib/types";

export function DocumentDetailView({ documentId }: { documentId: string }) {
  const router = useRouter();
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<
    "overview" | "medications" | "labs" | "allergies" | "events" | "text"
  >("overview");

  const loadDoc = useCallback(() => {
    setLoading(true);
    setError(null);
    api()
      .getDocument(documentId)
      .then((data) => {
        setDoc(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(toErrorMessage(err));
        setLoading(false);
      });
  }, [documentId]);

  useEffect(() => {
    loadDoc();
  }, [loadDoc]);

  // Poll status while document is processing
  useEffect(() => {
    if (doc?.status !== "processing") return;

    const interval = setInterval(() => {
      api()
        .getDocument(documentId)
        .then((updatedDoc) => {
          setDoc(updatedDoc);
          if (updatedDoc.status === "completed") {
            setSuccessMsg("Medical intelligence successfully extracted and persisted to your records!");
            queryClient.invalidateQueries({ queryKey: ["user"] });
          } else if (updatedDoc.status === "failed") {
            setError("Medical intelligence extraction failed. Please try again.");
          }
        })
        .catch(() => {});
    }, 2500);

    return () => clearInterval(interval);
  }, [doc?.status, documentId]);

  async function handleExtract() {
    setExtracting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await api().extractDocument(documentId);
      const updatedDoc = await api().getDocument(documentId);
      setDoc(updatedDoc);
    } catch (caught) {
      setError(toErrorMessage(caught));
    } finally {
      setExtracting(false);
    }
  }

  async function handleDelete() {
    if (!confirm("Are you sure you want to delete this medical document?")) return;
    setDeleting(true);
    try {
      await api().deleteDocument(documentId);
      router.push("/documents");
    } catch (caught) {
      setError(toErrorMessage(caught));
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[400px] w-full flex-col items-center justify-center gap-3 p-8">
        <Loader2 className="size-6 animate-spin text-brand-600" />
        <p className="text-sm text-neutral-500">Loading document intelligence...</p>
      </div>
    );
  }

  if (error && !doc) {
    return (
      <div className="flex w-full flex-col gap-4 p-6">
        <div
          role="alert"
          className="flex items-center justify-between gap-3 rounded-md border border-risk-high-border bg-risk-high-bg px-4 py-3 text-sm text-risk-high"
        >
          <span>{error}</span>
          <Button size="sm" variant="outline" onClick={loadDoc}>
            Retry
          </Button>
        </div>
        <Link
          href="/documents"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline"
        >
          <ArrowLeft className="size-4" />
          Back to documents
        </Link>
      </div>
    );
  }

  if (!doc) return null;

  const totalExtracted =
    doc.medications.length +
    doc.labResults.length +
    doc.allergies.length +
    doc.events.length;

  return (
    <div className="flex min-h-full w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
      {/* Top breadcrumb navigation */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/documents"
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-neutral-600 transition-colors hover:text-neutral-900"
        >
          <ArrowLeft className="size-4" />
          Back to Documents
        </Link>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={handleExtract}
            disabled={extracting || doc.status === "processing"}
            className="gap-1.5"
          >
            {extracting || doc.status === "processing" ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Sparkles className="size-3.5" />
            )}
            <span>
              {extracting || doc.status === "processing"
                ? "Processing..."
                : doc.status === "failed"
                ? "Retry AI"
                : "Extract AI"}
            </span>
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleDelete}
            disabled={deleting}
            className="border-risk-high text-risk-high hover:bg-risk-high-bg gap-1.5"
          >
            <Trash2 className="size-3.5" />
            <span>Delete</span>
          </Button>
        </div>
      </div>

      {successMsg && (
        <div
          role="status"
          className="flex items-center justify-between gap-3 rounded-md border border-status-ok-border bg-status-ok-bg px-3.5 py-2.5 text-[13px] text-status-ok"
        >
          <span>{successMsg}</span>
          <button
            type="button"
            onClick={() => setSuccessMsg(null)}
            className="text-xs font-semibold underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="rounded-md border border-risk-high-border bg-risk-high-bg px-3.5 py-2.5 text-[13px] text-risk-high"
        >
          {error}
        </div>
      )}

      {/* Document Header Card */}
      <div className="flex w-full flex-col gap-4 rounded-xl border border-neutral-200 bg-neutral-0 p-5 shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
              <FileText className="size-6" strokeWidth={1.8} />
            </span>
            <div className="flex flex-col gap-1">
              <h2 className="text-lg font-semibold tracking-[-0.2px] text-neutral-900">
                {doc.title}
              </h2>
              <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500">
                <span className="font-medium text-neutral-700">{doc.type}</span>
                <span>·</span>
                <span>Uploaded on {doc.uploadedAt}</span>
                {doc.processedAt && (
                  <>
                    <span>·</span>
                    <span>Processed {doc.processedAt}</span>
                  </>
                )}
              </div>
            </div>
          </div>
          <StatusPill status={doc.status} />
        </div>

        {/* Metadata Details Grid */}
        <div className="grid grid-cols-2 gap-3 border-t border-neutral-100 pt-4 sm:grid-cols-4 lg:grid-cols-6">
          <div className="flex flex-col gap-0.5">
            <span className="type-overline text-neutral-500">DOC TYPE</span>
            <span className="text-[13px] font-medium text-neutral-800">{doc.type}</span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="type-overline text-neutral-500">PAGES</span>
            <span className="text-[13px] font-medium text-neutral-800">{doc.pageCount || doc.pages}</span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="type-overline text-neutral-500">EXTRACTION METHOD</span>
            <span className="text-[13px] font-medium text-neutral-800 uppercase">
              {doc.extractionMethod || "NATIVE OCR"}
            </span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="type-overline text-neutral-500">DOCUMENT DATE</span>
            <span className="text-[13px] font-medium text-neutral-800">{doc.documentDate}</span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="type-overline text-neutral-500">AI CONFIDENCE</span>
            <span className="text-[13px] font-medium text-neutral-800">
              {doc.aiConfidence !== undefined ? `${doc.aiConfidence}%` : "—"}
            </span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="type-overline text-neutral-500">ENTITIES EXTRACTED</span>
            <span className="text-[13px] font-medium text-neutral-800">{totalExtracted}</span>
          </div>
        </div>
      </div>

      {/* AI Summary Banner if present */}
      {doc.aiSummary && (
        <div className="flex w-full flex-col gap-2 rounded-xl border border-brand-200 bg-brand-50/70 p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-brand-700" />
            <h3 className="text-sm font-semibold text-brand-900">Extracted Clinical Summary</h3>
          </div>
          <p className="text-[13px] leading-[21px] text-neutral-800">{doc.aiSummary}</p>
        </div>
      )}

      {/* Navigation Tabs for Extracted Details */}
      <div className="flex w-full border-b border-neutral-200">
        <button
          type="button"
          onClick={() => setActiveTab("overview")}
          className={cn(
            "cursor-pointer border-b-2 px-4 py-2.5 text-[13px] font-medium transition-colors",
            activeTab === "overview"
              ? "border-brand-600 text-brand-700 font-semibold"
              : "border-transparent text-neutral-500 hover:text-neutral-900"
          )}
        >
          Overview & Counts
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("medications")}
          className={cn(
            "cursor-pointer border-b-2 px-4 py-2.5 text-[13px] font-medium transition-colors",
            activeTab === "medications"
              ? "border-brand-600 text-brand-700 font-semibold"
              : "border-transparent text-neutral-500 hover:text-neutral-900"
          )}
        >
          Medications ({doc.medications.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("labs")}
          className={cn(
            "cursor-pointer border-b-2 px-4 py-2.5 text-[13px] font-medium transition-colors",
            activeTab === "labs"
              ? "border-brand-600 text-brand-700 font-semibold"
              : "border-transparent text-neutral-500 hover:text-neutral-900"
          )}
        >
          Lab Results ({doc.labResults.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("allergies")}
          className={cn(
            "cursor-pointer border-b-2 px-4 py-2.5 text-[13px] font-medium transition-colors",
            activeTab === "allergies"
              ? "border-brand-600 text-brand-700 font-semibold"
              : "border-transparent text-neutral-500 hover:text-neutral-900"
          )}
        >
          Allergies ({doc.allergies.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("events")}
          className={cn(
            "cursor-pointer border-b-2 px-4 py-2.5 text-[13px] font-medium transition-colors",
            activeTab === "events"
              ? "border-brand-600 text-brand-700 font-semibold"
              : "border-transparent text-neutral-500 hover:text-neutral-900"
          )}
        >
          Events ({doc.events.length})
        </button>
        {doc.extractedText && (
          <button
            type="button"
            onClick={() => setActiveTab("text")}
            className={cn(
              "cursor-pointer border-b-2 px-4 py-2.5 text-[13px] font-medium transition-colors",
              activeTab === "text"
                ? "border-brand-600 text-brand-700 font-semibold"
                : "border-transparent text-neutral-500 hover:text-neutral-900"
            )}
          >
            Raw Text
          </button>
        )}
      </div>

      {/* Tab Contents */}
      {activeTab === "overview" && (
        <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex items-center gap-3.5 rounded-xl border border-neutral-200 bg-neutral-0 p-4 shadow-card">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
              <Pill className="size-5" strokeWidth={1.8} />
            </span>
            <div className="flex flex-col">
              <span className="text-xl font-semibold text-neutral-900">{doc.medications.length}</span>
              <span className="type-overline text-neutral-500">MEDICATIONS EXTRACTED</span>
            </div>
          </div>
          <div className="flex items-center gap-3.5 rounded-xl border border-neutral-200 bg-neutral-0 p-4 shadow-card">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
              <Beaker className="size-5" strokeWidth={1.8} />
            </span>
            <div className="flex flex-col">
              <span className="text-xl font-semibold text-neutral-900">{doc.labResults.length}</span>
              <span className="type-overline text-neutral-500">LAB RESULTS EXTRACTED</span>
            </div>
          </div>
          <div className="flex items-center gap-3.5 rounded-xl border border-neutral-200 bg-neutral-0 p-4 shadow-card">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-risk-high-bg text-risk-high">
              <ShieldAlert className="size-5" strokeWidth={1.8} />
            </span>
            <div className="flex flex-col">
              <span className="text-xl font-semibold text-neutral-900">{doc.allergies.length}</span>
              <span className="type-overline text-neutral-500">ALLERGIES RECORDED</span>
            </div>
          </div>
          <div className="flex items-center gap-3.5 rounded-xl border border-neutral-200 bg-neutral-0 p-4 shadow-card">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-neutral-100 text-neutral-700">
              <Activity className="size-5" strokeWidth={1.8} />
            </span>
            <div className="flex flex-col">
              <span className="text-xl font-semibold text-neutral-900">{doc.events.length}</span>
              <span className="type-overline text-neutral-500">TIMELINE EVENTS</span>
            </div>
          </div>
        </div>
      )}

      {activeTab === "medications" && (
        <div className="w-full overflow-hidden rounded-xl border border-neutral-200 bg-neutral-0 shadow-card">
          <div className="w-full overflow-x-auto">
            <table className="w-full min-w-[700px] border-collapse text-left">
              <thead>
                <tr className="bg-neutral-50">
                  <th className="type-overline px-[18px] py-3 text-neutral-500">MEDICATION</th>
                  <th className="type-overline px-3 py-3 text-neutral-500">DOSAGE</th>
                  <th className="type-overline px-3 py-3 text-neutral-500">FREQUENCY</th>
                  <th className="type-overline px-3 py-3 text-neutral-500">INSTRUCTIONS</th>
                </tr>
              </thead>
              <tbody>
                {doc.medications.map((m) => (
                  <tr key={m.id} className="border-t border-neutral-200 hover:bg-neutral-50">
                    <td className="px-[18px] py-3">
                      <div className="flex flex-col">
                        <span className="text-[13px] font-semibold text-neutral-900">{m.name}</span>
                        {m.genericName && (
                          <span className="text-xs text-neutral-500">{m.genericName}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-[13px] text-neutral-700">{m.dosage || "—"}</td>
                    <td className="px-3 py-3 text-[13px] text-neutral-700">{m.frequency || "—"}</td>
                    <td className="px-3 py-3 text-[13px] text-neutral-600">{m.instructions || "—"}</td>
                  </tr>
                ))}
                {doc.medications.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-sm text-neutral-500">
                      No prescriptions extracted from this document.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === "labs" && (
        <div className="w-full overflow-hidden rounded-xl border border-neutral-200 bg-neutral-0 shadow-card">
          <div className="w-full overflow-x-auto">
            <table className="w-full min-w-[700px] border-collapse text-left">
              <thead>
                <tr className="bg-neutral-50">
                  <th className="type-overline px-[18px] py-3 text-neutral-500">TEST NAME</th>
                  <th className="type-overline px-3 py-3 text-neutral-500">VALUE / RESULT</th>
                  <th className="type-overline px-3 py-3 text-neutral-500">REFERENCE RANGE</th>
                  <th className="type-overline px-3 py-3 text-neutral-500">DATE</th>
                </tr>
              </thead>
              <tbody>
                {doc.labResults.map((l) => (
                  <tr key={l.id} className="border-t border-neutral-200 hover:bg-neutral-50">
                    <td className="px-[18px] py-3 text-[13px] font-semibold text-neutral-900">
                      {l.name}
                    </td>
                    <td className="px-3 py-3 text-[13px] font-medium text-neutral-800">
                      {l.latestValueLabel || l.latestValue} {l.unit}
                    </td>
                    <td className="px-3 py-3 text-[13px] text-neutral-500">{l.referenceRange || "—"}</td>
                    <td className="px-3 py-3 text-[13px] text-neutral-500">{l.latestDate}</td>
                  </tr>
                ))}
                {doc.labResults.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-sm text-neutral-500">
                      No lab results extracted from this document.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === "allergies" && (
        <div className="w-full overflow-hidden rounded-xl border border-neutral-200 bg-neutral-0 shadow-card">
          <div className="w-full overflow-x-auto">
            <table className="w-full min-w-[700px] border-collapse text-left">
              <thead>
                <tr className="bg-neutral-50">
                  <th className="type-overline px-[18px] py-3 text-neutral-500">ALLERGEN</th>
                  <th className="type-overline px-3 py-3 text-neutral-500">REACTION</th>
                  <th className="type-overline px-3 py-3 text-neutral-500">SEVERITY</th>
                </tr>
              </thead>
              <tbody>
                {doc.allergies.map((a) => (
                  <tr key={a.id} className="border-t border-neutral-200 hover:bg-neutral-50">
                    <td className="px-[18px] py-3 text-[13px] font-semibold text-neutral-900">
                      {a.medicationName}
                    </td>
                    <td className="px-3 py-3 text-[13px] text-neutral-700">{a.reaction || "Reported allergy"}</td>
                    <td className="px-3 py-3 text-[13px] capitalize font-medium text-risk-high">{a.severity || "Moderate"}</td>
                  </tr>
                ))}
                {doc.allergies.length === 0 && (
                  <tr>
                    <td colSpan={3} className="py-8 text-center text-sm text-neutral-500">
                      No drug allergies recorded in this document.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === "events" && (
        <div className="flex flex-col gap-3">
          {doc.events.map((e) => (
            <div key={e.id} className="flex flex-col gap-1 rounded-xl border border-neutral-200 bg-neutral-0 p-4 shadow-card">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold text-neutral-900">{e.title}</span>
                <span className="text-xs text-neutral-500">{e.date}</span>
              </div>
              <p className="text-[13px] text-neutral-700">{e.summary}</p>
            </div>
          ))}
          {doc.events.length === 0 && (
            <div className="rounded-xl border border-neutral-200 bg-neutral-0 py-8 text-center text-sm text-neutral-500">
              No timeline events recorded from this document.
            </div>
          )}
        </div>
      )}

      {activeTab === "text" && doc.extractedText && (
        <div className="rounded-xl border border-neutral-200 bg-neutral-0 p-4 shadow-card">
          <h4 className="type-overline mb-2 text-neutral-500">EXTRACTED CLINICAL TEXT</h4>
          <pre className="max-h-[500px] overflow-auto whitespace-pre-wrap rounded-lg bg-neutral-50 p-4 font-mono text-xs leading-5 text-neutral-800">
            {doc.extractedText}
          </pre>
        </div>
      )}

      {/* Safety notice */}
      <div className="flex w-full items-start gap-2.5 rounded-[10px] bg-neutral-50 px-4 py-3">
        <Info className="size-4 shrink-0 text-neutral-500" strokeWidth={1.8} />
        <p className="flex-1 text-[13px] leading-[19px] text-neutral-600">
          AI-extracted clinical entities from this document are provided for informational review. Please verify all prescriptions and laboratory findings with a licensed healthcare provider.
        </p>
      </div>
    </div>
  );
}
