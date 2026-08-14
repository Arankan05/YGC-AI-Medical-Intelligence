"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { FileText, FileWarning, Info, Loader2, Trash2, Upload } from "lucide-react";

import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { StatusPill } from "@/components/status-pill";
import { Button } from "@/components/ui/button";
import { api, toErrorMessage } from "@/lib/api";
import type { DocumentType, MedicalDocument } from "@/lib/types";

const CHIPS: FilterChip[] = [
  { value: "all", label: "All documents" },
  { value: "Lab Report", label: "Lab reports" },
  { value: "Prescription", label: "Prescriptions" },
  { value: "Doctor Note", label: "Doctor notes" },
  { value: "Discharge Summary", label: "Discharge summaries" },
];

export function DocumentsView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const query = (searchParams.get("q") ?? "").trim().toLowerCase();
  const [filter, setFilter] = useState<DocumentType | "all">("all");
  const [documents, setDocuments] = useState<MedicalDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function fetchDocuments() {
    setLoading(true);
    setError(null);
    api()
      .listDocuments()
      .then((docs) => {
        setDocuments(docs);
        setLoading(false);
      })
      .catch((caught) => {
        setError(toErrorMessage(caught));
        setLoading(false);
      });
  }

  useEffect(() => {
    fetchDocuments();
  }, []);

  async function handleDelete(docId: string, event: React.MouseEvent) {
    event.stopPropagation();
    if (!confirm("Are you sure you want to delete this medical document?")) return;
    setDeletingId(docId);
    try {
      await api().deleteDocument(docId);
      setDocuments((current) => current.filter((d) => d.id !== docId));
    } catch (caught) {
      setError(toErrorMessage(caught));
    } finally {
      setDeletingId(null);
    }
  }

  const rows = useMemo(
    () =>
      documents.filter((document) => {
        const matchesFilter = filter === "all" || document.type === filter;
        const matchesQuery =
          !query ||
          [document.title, document.type, document.provider]
            .join(" ")
            .toLowerCase()
            .includes(query);
        return matchesFilter && matchesQuery;
      }),
    [documents, filter, query]
  );

  return (
    <div className="flex w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
      {/* toolbar (23:487) */}
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <FilterChips
          label="Filter documents by type"
          chips={CHIPS}
          value={filter}
          onChange={(value) => setFilter(value as DocumentType | "all")}
        />
        <Button render={<Link href="/documents/upload" />} className="gap-2">
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
            onClick={fetchDocuments}
            className="border-risk-high text-risk-high hover:bg-risk-high-bg"
          >
            Retry
          </Button>
        </div>
      )}

      {query && (
        <p className="text-[13px] leading-[19px] text-neutral-500">
          {rows.length} result{rows.length === 1 ? "" : "s"} for &ldquo;{query}
          &rdquo; ·{" "}
          <Link href="/documents" className="font-medium text-brand-700 hover:underline">
            Clear search
          </Link>
        </p>
      )}

      {/* documents-table (23:505) */}
      <div className="w-full overflow-hidden rounded-xl border border-neutral-200 bg-neutral-0 shadow-card">
        <div className="w-full overflow-x-auto">
          <table className="w-full min-w-[860px] border-collapse text-left">
            <thead>
              <tr className="bg-neutral-50">
                <th className="type-overline px-[18px] py-3 text-neutral-500">
                  DOCUMENT
                </th>
                <th className="type-overline w-[160px] px-0 py-3 text-neutral-500">
                  TYPE
                </th>
                <th className="type-overline w-[140px] px-0 py-3 text-neutral-500">
                  MEDICAL DATE
                </th>
                <th className="type-overline w-[130px] px-0 py-3 text-neutral-500">
                  UPLOADED
                </th>
                <th className="type-overline w-[130px] px-0 py-3 text-neutral-500">
                  STATUS
                </th>
                <th className="type-overline w-[70px] px-3 py-3 text-right text-neutral-500">
                  ACTION
                </th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr className="border-t border-neutral-200">
                  <td colSpan={6} className="px-[18px] py-12 text-center text-neutral-500">
                    <div className="flex items-center justify-center gap-2 text-sm">
                      <Loader2 className="size-4 animate-spin text-brand-600" />
                      Loading documents...
                    </div>
                  </td>
                </tr>
              )}

              {!loading &&
                rows.map((document) => {
                  const failed = document.status === "failed";
                  const isDeleting = deletingId === document.id;
                  return (
                    <tr
                      key={document.id}
                      className="border-t border-neutral-200 transition-colors hover:bg-neutral-50"
                    >
                      <td className="px-[18px] py-[13px]">
                        <div className="flex items-center gap-3">
                          <span
                            className={`flex size-8 shrink-0 items-center justify-center rounded-md ${
                              failed ? "bg-risk-high-bg" : "bg-neutral-100"
                            }`}
                          >
                            {failed ? (
                              <FileWarning
                                className="size-[15px] text-risk-high"
                                strokeWidth={1.8}
                              />
                            ) : (
                              <FileText
                                className="size-[15px] text-neutral-600"
                                strokeWidth={1.8}
                              />
                            )}
                          </span>
                          <span className="flex flex-col gap-0.5">
                            <span className="text-[13px] leading-[18px] font-medium text-neutral-800">
                              {document.title}
                            </span>
                            <span className="text-xs leading-4 font-medium text-neutral-500">
                              {document.sizeLabel}
                            </span>
                          </span>
                        </div>
                      </td>
                      <td className="py-[13px] text-[13px] leading-[19px] text-neutral-600">
                        {failed ? "—" : document.type}
                      </td>
                      <td className="py-[13px] text-[13px] leading-[19px] text-neutral-600">
                        {document.documentDate}
                      </td>
                      <td className="py-[13px] text-[13px] leading-[19px] text-neutral-500">
                        {document.uploadedAt}
                      </td>
                      <td className="py-[13px]">
                        <StatusPill status={document.status} />
                      </td>
                      <td className="px-3 py-[13px] text-right">
                        <button
                          type="button"
                          disabled={isDeleting}
                          onClick={(e) => handleDelete(document.id, e)}
                          className="inline-flex size-7 items-center justify-center rounded text-neutral-400 transition-colors hover:bg-risk-high-bg hover:text-risk-high disabled:opacity-50"
                          title="Delete document"
                          aria-label={`Delete ${document.title}`}
                        >
                          <Trash2 className="size-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}

              {!loading && rows.length === 0 && (
                <tr className="border-t border-neutral-200">
                  <td colSpan={6} className="px-[18px] py-12 text-center">
                    <p className="text-sm leading-[21px] text-neutral-600">
                      {filter === "all"
                        ? "No documents uploaded yet. Upload a document to get started."
                        : "No documents match this filter."}
                    </p>
                    {filter !== "all" ? (
                      <button
                        type="button"
                        onClick={() => {
                          setFilter("all");
                          router.push("/documents");
                        }}
                        className="mt-2 cursor-pointer text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                      >
                        Show all documents
                      </button>
                    ) : (
                      <Link
                        href="/documents/upload"
                        className="mt-2 inline-block cursor-pointer text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                      >
                        Upload your first document
                      </Link>
                    )}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* processing note (23:650) */}
      <div className="flex w-full items-start gap-2.5 rounded-[10px] bg-neutral-50 px-4 py-3">
        <Info className="size-4 shrink-0 text-neutral-500" strokeWidth={1.8} />
        <p className="flex-1 text-[13px] leading-[19px] text-neutral-600">
          PDFs with selectable text are parsed with PyMuPDF. Scanned pages and
          images fall back to Tesseract OCR automatically. Unsupported file types
          are rejected at validation rather than partially processed.
        </p>
      </div>
    </div>
  );
}
