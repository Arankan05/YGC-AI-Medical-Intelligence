"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Beaker,
  Building2,
  Calendar,
  FileText,
  Pill,
  Upload,
  type LucideIcon,
} from "lucide-react";

import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { Panel } from "@/components/panel";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { RiskLevel, TimelineEvent, TimelineEventKind } from "@/lib/types";

const CHIPS: FilterChip[] = [
  { value: "all", label: "All events" },
  { value: "prescription", label: "Prescriptions" },
  { value: "lab", label: "Lab results" },
  { value: "note", label: "Doctor notes" },
  { value: "allergy", label: "Allergies" },
  { value: "visit", label: "Admissions" },
];

const KIND_STYLES: Record<
  TimelineEventKind,
  { icon: LucideIcon; slot: string; ink: string }
> = {
  prescription: {
    icon: Pill,
    slot: "bg-status-info-bg",
    ink: "text-status-info",
  },
  note: { icon: FileText, slot: "bg-risk-med-bg", ink: "text-risk-med" },
  lab: { icon: Beaker, slot: "bg-brand-50", ink: "text-brand-700" },
  visit: { icon: Building2, slot: "bg-neutral-100", ink: "text-neutral-600" },
  imaging: { icon: Beaker, slot: "bg-brand-50", ink: "text-brand-700" },
};

export function TimelineView() {
  const [filter, setFilter] = useState("all");
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    api()
      .listTimeline()
      .then((data) => {
        if (active) {
          setEvents(data || []);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const filtered = useMemo(
    () =>
      events.filter((item) => {
        if (filter === "all") return true;
        return item.kind === filter;
      }),
    [events, filter]
  );

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
          <span>Timeline Range: —</span>
        </div>
      </div>

      {/* timeline body */}
      <Panel className="p-6">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
            <p className="text-sm leading-5 text-neutral-600">
              No medical events on your timeline yet. Events will appear here once extracted from your uploaded medical records.
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
          <div className="flex flex-col gap-6">
            {filtered.map((item) => {
              const style = KIND_STYLES[item.kind] ?? KIND_STYLES.note;
              const Icon = style.icon;
              return (
                <div key={item.id} className="flex gap-4">
                  <span
                    className={cn(
                      "flex size-9 shrink-0 items-center justify-center rounded-lg",
                      style.slot
                    )}
                  >
                    <Icon className={cn("size-4", style.ink)} strokeWidth={1.8} />
                  </span>
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium text-neutral-900">
                      {item.title}
                    </p>
                    <p className="text-xs text-neutral-500">
                      {item.date} · {item.provider}
                    </p>
                    <p className="text-xs text-neutral-600">
                      {item.summary}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}
