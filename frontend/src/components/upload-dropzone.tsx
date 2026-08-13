"use client";

import { useRef, useState, type DragEvent } from "react";
import { FileUp, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const ACCEPTED_FILE_TYPES = ".pdf,.jpg,.jpeg,.png,.tif,.tiff";
const FORMAT_CHIPS = ["PDF", "JPG", "PNG", "TIFF", "up to 20 MB each"];

/**
 * Figma: `panel · dropzone` (nodes 39:1656 / 24:315) — dashed brand dropzone
 * with a round icon badge, headline, copy, browse button and format chips.
 */
export function UploadDropzone({
  title,
  description,
  buttonLabel = "Browse files",
  onFiles,
  className,
}: {
  title: string;
  description: string;
  buttonLabel?: string;
  onFiles: (files: File[]) => void;
  className?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    const files = Array.from(event.dataTransfer.files ?? []);
    if (files.length > 0) onFiles(files);
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={handleDrop}
      className={cn(
        // 39:1657 — horizontal padding only; the frame fills its panel and centres.
        "flex w-full flex-1 flex-col items-center justify-center gap-3.5 rounded-[11px] border-[1.5px] border-dashed border-brand-200 bg-brand-50 px-10 text-center transition-colors",
        dragActive && "border-brand-700 bg-brand-100",
        className
      )}
    >
      <span className="flex size-[68px] items-center justify-center rounded-full bg-neutral-0">
        <Upload className="size-[30px] text-brand-700" strokeWidth={1.8} />
      </span>
      <p className="text-[22px] leading-[30px] font-semibold tracking-[-0.3px] text-neutral-900">
        {title}
      </p>
      <p className="max-w-[520px] text-sm leading-[21px] text-neutral-600">
        {description}
      </p>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED_FILE_TYPES}
        className="sr-only"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          if (files.length > 0) onFiles(files);
          event.target.value = "";
        }}
      />
      <Button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="rounded-[9px] px-5 py-3"
      >
        <FileUp className="size-4" strokeWidth={1.8} />
        {buttonLabel}
      </Button>
      <div className="flex flex-wrap items-center justify-center gap-2 pt-0.5">
        {FORMAT_CHIPS.map((chip) => (
          <span
            key={chip}
            className="rounded-full border border-brand-200 bg-neutral-0 px-2.5 py-1 text-xs leading-4 font-medium text-neutral-600"
          >
            {chip}
          </span>
        ))}
      </div>
    </div>
  );
}
