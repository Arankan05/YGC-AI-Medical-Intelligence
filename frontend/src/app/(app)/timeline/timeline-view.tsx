"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  Beaker,
  Building2,
  Calendar,
  FileText,
  Pill,
  type LucideIcon,
} from "lucide-react";

import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { Panel } from "@/components/panel";
import { timelineEvents, timelineRange } from "@/lib/data";
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

const TAG_STYLES: Record<RiskLevel, string> = {
  high: "bg-risk-high-bg text-risk-high",
  medium: "bg-risk-med-bg text-risk-med",
  low: "bg-risk-low-bg text-risk-low",
};

function monthLabel(date: string) {
  // "12 Jun 2026" -> "JUNE 2026"
  const [, month, year] = date.split(" ");
  const full: Record<string, string> = {
    Jan: "JANUARY",
    Feb: "FEBRUARY",
    Mar: "MARCH",
    Apr: "APRIL",
    May: "MAY",
    Jun: "JUNE",
    Jul: "JULY",
    Aug: "AUGUST",
    Sep: "SEPTEMBER",
    Oct: "OCTOBER",
    Nov: "NOVEMBER",
    Dec: "DECEMBER",
  };
  return `${full[month] ?? month.toUpperCase()} ${year}`;
}

export function TimelineView() {
  const [filter, setFilter] = useState("all");

  const groups = useMemo(() => {
    const filtered = timelineEvents.filter((event) => {
      if (filter === "all") return true;
      if (filter === "allergy")
        return event.tags.some((tag) => tag.toLowerCase().includes("allergy"));
      return event.kind === filter;
    });

    const byMonth = new Map<string, TimelineEvent[]>();
    for (const event of filtered) {
      const key = monthLabel(event.date);
      byMonth.set(key, [...(byMonth.get(key) ?? []), event]);
    }
    return Array.from(byMonth.entries());
  }, [filter]);

  return (
    <div className="flex h-full w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
      {/* toolbar (25:491) */}
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <FilterChips
          label="Filter timeline events"
          chips={CHIPS}
          value={filter}
          onChange={setFilter}
        />
        <button
          type="button"
          className="flex cursor-default items-center gap-2 rounded-md border border-neutral-200 bg-neutral-0 px-3.5 py-2 text-[13px] leading-[18px] font-medium text-neutral-700"
        >
          <Calendar className="size-[15px] text-neutral-600" strokeWidth={1.8} />
          {timelineRange}
        </button>
      </div>

      {/* panel · timeline (25:512) */}
      <Panel className="min-h-0 flex-1 overflow-hidden">
        <div className="scrollbar-thin flex min-h-0 w-full flex-1 flex-col overflow-y-auto px-4 py-5 md:px-[22px]">
          {groups.length === 0 && (
            <p className="py-16 text-center text-sm leading-[21px] text-neutral-600">
              No events of this type in the selected range.
            </p>
          )}
          {groups.map(([month, events]) => (
            <div key={month} className="flex w-full flex-col">
              <div className="flex w-full items-center gap-3 pt-1.5 pb-3">
                <span className="type-overline rounded-full bg-neutral-100 px-3 py-1 text-neutral-600">
                  {month}
                </span>
                <span className="h-px flex-1 bg-neutral-200" />
              </div>
              {events.map((event) => {
                const style = KIND_STYLES[event.kind];
                const Icon = style.icon;
                return (
                  <article
                    key={event.id}
                    className="flex w-full items-start gap-3.5 pb-3"
                  >
                    <div className="flex w-[34px] shrink-0 flex-col items-center self-stretch">
                      <span
                        className={cn(
                          "flex size-[34px] shrink-0 items-center justify-center rounded-full",
                          style.slot
                        )}
                      >
                        <Icon
                          className={cn("size-4", style.ink)}
                          strokeWidth={1.8}
                        />
                      </span>
                      <span className="w-0.5 flex-1 bg-neutral-200" />
                    </div>
                    <div className="flex min-w-0 flex-1 flex-col gap-[7px] rounded-[10px] border border-neutral-200 bg-neutral-0 px-[15px] py-3">
                      <div className="flex w-full flex-wrap items-center justify-between gap-2">
                        <h3 className="text-sm leading-5 font-medium text-neutral-900">
                          {event.title}
                        </h3>
                        <span className="text-xs leading-4 font-medium text-neutral-600">
                          {event.date}
                        </span>
                      </div>
                      <p className="text-[13px] leading-[19px] text-neutral-600">
                        {event.summary}
                      </p>
                      <div className="flex flex-wrap items-center gap-2.5">
                        <Link
                          href="/documents"
                          className="flex items-center gap-1.5 text-xs leading-4 font-medium text-brand-700 hover:underline"
                        >
                          <FileText className="size-[13px]" strokeWidth={1.8} />
                          {event.documentTitle}
                        </Link>
                        {event.tags.map((tag) => (
                          <span
                            key={tag}
                            className={cn(
                              "type-overline rounded-full px-2 py-[3px]",
                              TAG_STYLES[event.risk ?? "low"]
                            )}
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
