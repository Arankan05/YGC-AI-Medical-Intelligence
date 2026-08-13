"use client";

import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Bell, Menu, Search } from "lucide-react";

import { RiskBadge } from "@/components/risk-badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import type { Finding } from "@/lib/types";

/**
 * Figma: App Top Bar (node 14:2)
 * Page header — the title and subtitle are overridden per screen.
 */
export function AppTopBar({
  title,
  subtitle,
  notifications = [],
  onOpenNav,
  className,
}: {
  title: string;
  subtitle: string;
  notifications?: Finding[];
  onOpenNav?: () => void;
  className?: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const value = query.trim();
    router.push(value ? `/documents?q=${encodeURIComponent(value)}` : "/documents");
  }

  return (
    <header
      className={cn(
        "flex h-[72px] w-full shrink-0 items-center justify-between gap-4 border-b border-neutral-200 bg-neutral-0 px-4 md:px-7",
        className
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onOpenNav}
          aria-label="Open navigation"
          className="flex size-[38px] shrink-0 items-center justify-center rounded-md border border-neutral-200 text-neutral-600 lg:hidden"
        >
          <Menu className="size-[17px]" strokeWidth={1.8} />
        </button>
        <div className="flex min-w-0 flex-col gap-0.5">
          <h1 className="truncate text-lg leading-[26px] font-semibold tracking-[-0.2px] text-neutral-900">
            {title}
          </h1>
          <p className="truncate text-[13px] leading-[19px] text-neutral-500">
            {subtitle}
          </p>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2.5">
        <form onSubmit={handleSubmit} className="hidden md:block" role="search">
          <label className="flex h-[38px] w-[220px] items-center gap-[9px] rounded-md border border-neutral-200 bg-neutral-50 px-3 focus-within:border-brand-700 xl:w-[300px]">
            <Search className="size-4 shrink-0 text-neutral-500" strokeWidth={1.8} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search records, medications, tests…"
              aria-label="Search records, medications, tests"
              className="w-full bg-transparent text-[13px] leading-[19px] text-neutral-900 outline-none placeholder:text-neutral-600"
            />
          </label>
        </form>

        <Popover>
          <PopoverTrigger
            aria-label={`Notifications${
              notifications.length ? ` (${notifications.length} new)` : ""
            }`}
            className="relative flex size-[38px] items-center justify-center rounded-md border border-neutral-200 bg-neutral-0 text-neutral-600 outline-none transition-colors hover:bg-neutral-50 focus-visible:ring-3 focus-visible:ring-brand-700/25"
          >
            <Bell className="size-[17px]" strokeWidth={1.8} />
            {notifications.length > 0 && (
              <span className="absolute top-1.5 right-1.5 size-2 rounded-full border-2 border-neutral-0 bg-risk-high" />
            )}
          </PopoverTrigger>
          <PopoverContent align="end" className="w-[320px] p-0">
            <div className="border-b border-neutral-200 px-4 py-3">
              <p className="text-[13px] leading-[18px] font-medium text-neutral-900">
                Recent AI findings
              </p>
            </div>
            <ul className="max-h-[320px] overflow-y-auto">
              {notifications.length === 0 && (
                <li className="px-4 py-6 text-center text-[13px] text-neutral-500">
                  Nothing needs your attention right now.
                </li>
              )}
              {notifications.map((finding) => (
                <li key={finding.id} className="border-b border-neutral-200 last:border-b-0">
                  <Link
                    href={`/findings/${finding.id}`}
                    className="flex flex-col gap-1.5 px-4 py-3 transition-colors hover:bg-neutral-50"
                  >
                    <RiskBadge risk={finding.risk} />
                    <span className="text-[13px] leading-[18px] font-medium text-neutral-900">
                      {finding.title}
                    </span>
                    <span className="text-xs leading-4 text-neutral-500">
                      Detected {finding.detectedOn}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
            <div className="border-t border-neutral-200 px-4 py-2.5">
              <Link
                href="/findings"
                className="text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
              >
                View all findings
              </Link>
            </div>
          </PopoverContent>
        </Popover>
      </div>
    </header>
  );
}
