"use client";

import { useRef, useState, type DragEvent } from "react";
import { Check, Upload, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { api, toErrorMessage } from "@/lib/api";
import { demoUploadItems, uploadPipelineSteps } from "@/lib/data";
import { cn } from "@/lib/utils";
import type { PipelineStep, UploadItem } from "@/lib/types";

const ACCEPTED_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"];
const MAX_BYTES = 20 * 1024 * 1024;

function formatSize(bytes: number) {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** Client-side validation mirroring the "rejected at validation" row in the design. */
function toUploadItem(file: File, index: number): UploadItem {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  const sizeLabel = formatSize(file.size);

  if (!ACCEPTED_EXTENSIONS.includes(extension)) {
    return {
      id: `${file.name}-${index}`,
      fileName: file.name,
      sizeLabel,
      progress: 0,
      status: "failed",
      message: "Unsupported file type — rejected at validation",
    };
  }
  if (file.size > MAX_BYTES) {
    return {
      id: `${file.name}-${index}`,
      fileName: file.name,
      sizeLabel,
      progress: 0,
      status: "failed",
      message: "Larger than 20 MB — rejected at validation",
    };
  }
  return {
    id: `${file.name}-${index}`,
    fileName: file.name,
    sizeLabel,
    progress: 0,
    status: "uploading",
    message:
      extension === "pdf"
        ? "Ready to process · text layer will be read with PyMuPDF"
        : "Ready to process · scanned image will run through OCR",
  };
}

function pipelineFor(items: UploadItem[], processing: boolean): PipelineStep[] {
  if (items === demoUploadItems) return uploadPipelineSteps;
  const validated = items.some((item) => item.status !== "failed");
  return uploadPipelineSteps.map((step, index) => {
    if (step.id === "validate")
      return { ...step, status: validated ? "done" : "failed" };
    if (!processing) return { ...step, status: "pending" };
    return { ...step, status: index <= 2 ? "done" : "active" };
  });
}

export function UploadModal({
  open,
  onOpenChange,
  initialFiles = [],
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialFiles?: File[];
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>(initialFiles);
  const [dragActive, setDragActive] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const staged = files.map(toUploadItem);
  /** With nothing staged the modal shows the pipeline state exactly as designed. */
  const items = staged.length > 0 ? staged : demoUploadItems;
  const steps = pipelineFor(items, processing);
  const processable = items.filter((item) => item.status !== "failed").length;

  function addFiles(incoming: File[]) {
    setError(null);
    setFiles((current) => [...current, ...incoming]);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    const dropped = Array.from(event.dataTransfer.files ?? []);
    if (dropped.length > 0) addFiles(dropped);
  }

  async function handleProcess() {
    setProcessing(true);
    setError(null);
    try {
      for (const file of files) {
        await api().uploadDocument({ file });
      }
      onOpenChange(false);
    } catch (caught) {
      setError(toErrorMessage(caught));
    } finally {
      setProcessing(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="w-[600px] max-w-[calc(100vw-32px)] gap-0 rounded-2xl border-0 p-0 shadow-[0px_18px_48px_-8px_rgba(15,23,42,0.2)] sm:max-w-[600px]"
      >
        {/* header (24:486) */}
        <div className="flex items-center justify-between gap-4 pt-5 pr-5 pb-[18px] pl-6">
          <div className="flex min-w-0 flex-col gap-[3px]">
            <DialogTitle className="text-lg leading-[26px] font-semibold tracking-[-0.2px] text-neutral-900">
              Upload medical documents
            </DialogTitle>
            <DialogDescription className="text-[13px] leading-[19px] text-neutral-500">
              Lab reports, prescriptions, doctor notes or discharge summaries
            </DialogDescription>
          </div>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            aria-label="Close"
            className="flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-md bg-neutral-100 text-neutral-600 transition-colors outline-none hover:bg-neutral-200 focus-visible:ring-3 focus-visible:ring-brand-700/25"
          >
            <X className="size-[15px]" strokeWidth={1.8} />
          </button>
        </div>

        {/* modal-body (24:494) */}
        <div className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto px-6 pt-1 pb-5">
          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            className={cn(
              "flex w-full flex-col items-center gap-2 rounded-xl border-[1.5px] border-dashed border-brand-200 bg-brand-50 px-6 py-[30px] text-center transition-colors",
              dragActive && "border-brand-700 bg-brand-100"
            )}
          >
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="flex size-[46px] cursor-pointer items-center justify-center rounded-xl bg-neutral-0 transition-colors hover:bg-white"
              aria-label="Browse your device"
            >
              <Upload className="size-[21px] text-brand-700" strokeWidth={1.8} />
            </button>
            <p className="text-sm leading-5 font-medium text-neutral-800">
              Drag files here, or browse your device
            </p>
            <p className="text-[13px] leading-[19px] text-neutral-500">
              PDF, JPG, PNG · up to 20 MB per file · multiple files supported
            </p>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".pdf,.jpg,.jpeg,.png"
              className="sr-only"
              onChange={(event) => {
                const picked = Array.from(event.target.files ?? []);
                if (picked.length > 0) addFiles(picked);
                event.target.value = "";
              }}
            />
          </div>

          {/* file list (24:503) */}
          <ul className="flex w-full flex-col gap-2.5">
            {items.map((item) => {
              const failed = item.status === "failed";
              const inProgress =
                item.status === "extracting" || item.status === "processing";
              return (
                <li
                  key={item.id}
                  className={cn(
                    "flex w-full flex-col gap-[9px] rounded-[10px] border px-3.5 py-3",
                    failed
                      ? "border-risk-high-border bg-risk-high-bg"
                      : "border-neutral-200 bg-neutral-50"
                  )}
                >
                  <div className="flex w-full items-center gap-[11px]">
                    <span
                      className={cn(
                        "flex size-[22px] shrink-0 items-center justify-center rounded-full text-neutral-0",
                        failed
                          ? "bg-risk-high"
                          : inProgress
                            ? "bg-brand-700"
                            : "bg-status-ok"
                      )}
                    >
                      {failed ? (
                        <X className="size-3" strokeWidth={2.4} />
                      ) : inProgress ? (
                        <Upload className="size-3" strokeWidth={2.4} />
                      ) : (
                        <Check className="size-3" strokeWidth={2.4} />
                      )}
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="truncate text-[13px] leading-[18px] font-medium text-neutral-800">
                        {item.fileName}
                      </span>
                      <span
                        className={cn(
                          "text-xs leading-4 font-medium",
                          failed ? "text-risk-high" : "text-neutral-500"
                        )}
                      >
                        {item.sizeLabel}
                        {item.message ? ` · ${item.message}` : ""}
                      </span>
                    </span>
                    {inProgress && (
                      <span className="text-xs leading-4 font-semibold text-neutral-700">
                        {item.progress}%
                      </span>
                    )}
                  </div>
                  {inProgress && (
                    <div className="h-[5px] w-full overflow-hidden rounded-full bg-neutral-200">
                      <div
                        className="h-[5px] rounded-full bg-brand-600 transition-[width]"
                        style={{ width: `${item.progress}%` }}
                      />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>

          {/* PROCESSING PIPELINE (24:534) */}
          <div className="flex w-full flex-col gap-3 rounded-[10px] bg-neutral-50 px-4 py-3.5">
            <p className="type-overline text-neutral-500">PROCESSING PIPELINE</p>
            <ol className="flex w-full flex-wrap items-start justify-between gap-y-3">
              {steps.map((step) => (
                <li
                  key={step.id}
                  title={step.description}
                  className="flex flex-col items-center gap-[7px] px-1"
                >
                  <span
                    className={cn(
                      "flex size-5 items-center justify-center rounded-full",
                      step.status === "done" && "bg-brand-700 text-neutral-0",
                      step.status === "active" &&
                        "border-2 border-brand-600 bg-brand-100",
                      step.status === "pending" && "bg-neutral-200",
                      step.status === "failed" && "bg-risk-high text-neutral-0"
                    )}
                  >
                    {step.status === "done" && (
                      <Check className="size-[11px]" strokeWidth={2.6} />
                    )}
                    {step.status === "failed" && (
                      <X className="size-[11px]" strokeWidth={2.6} />
                    )}
                  </span>
                  <span
                    className={cn(
                      "text-xs leading-4 font-medium",
                      step.status === "pending"
                        ? "text-neutral-600"
                        : "text-neutral-700"
                    )}
                  >
                    {step.title}
                  </span>
                </li>
              ))}
            </ol>
          </div>

          {error && (
            <p
              role="alert"
              className="rounded-[10px] border border-risk-high-border bg-risk-high-bg px-3.5 py-2.5 text-[13px] leading-[19px] text-risk-high"
            >
              {error}
            </p>
          )}
        </div>

        {/* footer (24:564) */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-b-2xl bg-neutral-50 px-6 pt-4 pb-[18px]">
          <p className="text-[13px] leading-[19px] text-neutral-500">
            Private to your account.
          </p>
          <div className="flex items-center gap-2.5">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleProcess}
              disabled={processable === 0 || processing}
            >
              {processing
                ? "Processing…"
                : `Process ${processable} file${processable === 1 ? "" : "s"}`}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
