"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Beaker,
  Building2,
  Calendar,
  FileText,
  Info,
  Loader2,
  Pill,
  Upload,
  type LucideIcon,
} from "lucide-react";

import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { Panel } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { api, toErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { TimelineEvent, TimelineEventKind } from "@/lib/types";

const CHIPS: FilterChip[] = [
  { value: "all", label: "All events" },
  { value: "prescription", label: "Prescriptions" },
  { value: "lab", label: "Lab results" },
  { value: "note", label: "Doctor notes" },
  { value: "allergy", label: "Allergies" },
  { value: "visit", label: "Consultations & visits" },
];

const KIND_STYLES: Record<
  TimelineEventKind,
  { icon: LucideIcon; slot: string; ink: string; label: string }
> = {
  prescription: {
    icon: Pill,
    slot: "bg-status-info-bg border-status-info-border",
    ink: "text-status-info",
    label: "Prescription",
  },
  note: {
    icon: FileText,
    slot: "bg-risk-med-bg border-risk-med-border",
    ink: "text-risk-med",
    label: "Clinical Note",
  },
  lab: {
    icon: Beaker,
    slot: "bg-brand-50 border-brand-200",
    ink: "text-brand-700",
    label: "Lab Test",
  },
  visit: {
    icon: Building2,
    slot: "bg-neutral-100 border-neutral-200",
    ink: "text-neutral-700",
    label: "Visit / Consultation",
  },
  imaging: {
    icon: Beaker,
    slot: "bg-brand-50 border-brand-200",
    ink: "text-brand-700",
    label: "Imaging",
  },
};

export function TimelineView() {
  const [filter, setFilter] = useState("all");
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function loadTimeline() {
    setLoading(true);
    setError(null);
    api()
      .listTimeline()
      .then((data) => {
        setEvents(data || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(toErrorMessage(err));
        setLoading(false);
      });
  }

  useEffect(() => {
    loadTimeline();
  }, []);

  const filtered = useMemo(
    () =>
      events.filter((item) => {
        if (filter === "all") return true;
        return item.kind === filter;
      }),
    [events, filter]
  );

  const dateRangeLabel = useMemo(() => {
    if (events.length === 0) return "No events recorded";
    const dates = events.map((e) => e.date).filter(Boolean);
    if (dates.length === 0) return "—";
    if (dates.length === 1) return dates[0];
    return `${dates[dates.length - 1]} – ${dates[0]}`;
  }, [events]);

  return (
    <div className="flex w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
      {/* toolbar */}
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <FilterChips
          label="Filter timeline events"
          chips={CHIPS}
          value={filter}
          onChange={setFilter}
        />
        <div className="flex items-center gap-2 text-xs leading-4 font-medium text-neutral-500">
          <Calendar className="size-3.5" strokeWidth={1.8} />
          <span>Timeline Range: {dateRangeLabel}</span>
        </div>
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
            onClick={loadTimeline}
            className="border-risk-high text-risk-high hover:bg-risk-high-bg"
          >
            Retry
          </Button>
        </div>
      )}

      {/* timeline body */}
      <Panel className="p-6">
        {loading ? (
          <div className="flex flex-col items-center justify-center gap-2 py-16 text-center text-sm text-neutral-500">
            <Loader2 className="size-5 animate-spin text-brand-600" />
            <span>Loading chronological timeline...</span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <p className="text-sm leading-5 text-neutral-600">
              {filter === "all"
                ? "No medical events on your timeline yet. Events will appear here once extracted from your uploaded medical records."
                : "No timeline events match this category filter."}
            </p>
            <Link
              href="/documents/upload"
              className="inline-flex items-center gap-1.5 text-[13px] font-medium text-brand-700 hover:underline"
            >
              <Upload className="size-3.5" />
              Upload medical documents
            </Link>
          </div>
        ) : (
          <div className="relative flex flex-col gap-6 pl-2">
            {/* Vertical connector line */}
            <div className="absolute top-4 bottom-4 left-[26px] w-[2px] bg-neutral-200" />

            {filtered.map((item) => {
              const style = KIND_STYLES[item.kind] ?? KIND_STYLES.note;
              const Icon = style.icon;
              return (
                <div key={item.id} className="relative flex items-start gap-4">
                  <span
                    className={cn(
                      "relative z-10 flex size-10 shrink-0 items-center justify-center rounded-xl border bg-neutral-0 shadow-sm",
                      style.slot
                    )}
                  >
                    <Icon className={cn("size-5", style.ink)} strokeWidth={1.8} />
                  </span>
                  <div className="flex flex-1 flex-col gap-1 rounded-xl border border-neutral-200 bg-neutral-0 p-4 shadow-card">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="type-overline rounded-full bg-neutral-100 px-2 py-0.5 text-neutral-600">
                          {style.label}
                        </span>
                        <h3 className="text-sm font-semibold text-neutral-900">
                          {item.title}
                        </h3>
                      </div>
                      <span className="text-xs font-medium text-neutral-500">
                        {item.date}
                      </span>
                    </div>
                    {item.summary && (
                      <p className="text-[13px] leading-[20px] text-neutral-700">
                        {item.summary}
                      </p>
                    )}
                    {item.provider && (
                      <span className="text-xs text-neutral-500">
                        {item.provider}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>

      {/* Safety notice */}
      <div className="flex w-full items-start gap-2.5 rounded-[10px] bg-neutral-50 px-4 py-3">
        <Info className="size-4 shrink-0 text-neutral-500" strokeWidth={1.8} />
        <p className="flex-1 text-[13px] leading-[19px] text-neutral-600">
          Medical events are automatically extracted from your medical documents in chronological order. Please consult with a healthcare professional to confirm any clinical diagnoses or historical procedures.
        </p>
      </div>
    </div>
  );
}
