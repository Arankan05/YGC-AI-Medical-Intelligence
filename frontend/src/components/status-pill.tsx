import { cn } from "@/lib/utils";
import type { DocumentStatus } from "@/lib/types";

/**
 * Figma: Design System / Status Pill (node 11:24)
 * Document processing state: Uploading, Processing, Extracting, Analyzing, Completed, Failed.
 */
const STATUS_STYLES: Record<
  DocumentStatus,
  { wrap: string; dot: string; text: string; label: string }
> = {
  completed: {
    wrap: "bg-status-ok-bg",
    dot: "bg-status-ok",
    text: "text-status-ok",
    label: "Completed",
  },
  uploading: {
    wrap: "bg-status-pending-bg",
    dot: "bg-status-pending",
    text: "text-status-pending",
    label: "Uploading",
  },
  processing: {
    wrap: "bg-status-pending-bg",
    dot: "bg-status-pending",
    text: "text-status-pending",
    label: "Processing",
  },
  extracting: {
    wrap: "bg-status-info-bg",
    dot: "bg-status-info",
    text: "text-status-info",
    label: "Extracting",
  },
  analyzing: {
    wrap: "bg-status-pending-bg",
    dot: "bg-status-pending",
    text: "text-status-pending",
    label: "Analyzing",
  },
  failed: {
    wrap: "bg-risk-high-bg",
    dot: "bg-risk-high",
    text: "text-risk-high",
    label: "Failed",
  },
};

export function StatusPill({
  status,
  label,
  className,
}: {
  status: DocumentStatus;
  label?: string;
  className?: string;
}) {
  const s = STATUS_STYLES[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full py-[3px] pr-2.5 pl-2",
        s.wrap,
        className
      )}
    >
      <span className={cn("size-[5px] shrink-0 rounded-full", s.dot)} />
      <span className={cn("text-xs leading-4 font-semibold", s.text)}>
        {label ?? s.label}
      </span>
    </span>
  );
}
