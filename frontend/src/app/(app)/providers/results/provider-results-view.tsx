"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Clock,
  Info,
  MapPin,
  MapPinOff,
  Move,
  Phone,
  PhoneOff,
  RefreshCw,
  SearchX,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";

import { ProviderMap } from "@/components/provider-map";
import { Button } from "@/components/ui/button";
import {
  providerEmptyState,
  providerErrorState,
  providerRankingWeights,
  providerResultsNote,
  providers,
} from "@/lib/data";
import { cn } from "@/lib/utils";
import type { Provider } from "@/lib/types";

const BREAKDOWN_COLORS = [
  "bg-brand-700",
  "bg-brand-500",
  "bg-brand-200",
  "bg-neutral-300",
];

function ProviderCard({
  provider,
  rank,
}: {
  provider: Provider;
  rank: number;
}) {
  const top = rank === 1;
  return (
    <article
      className={cn(
        "flex w-full flex-col gap-2.5 rounded-[11px] border px-[15px] py-[13px]",
        top
          ? "border-brand-200 bg-brand-50"
          : "border-neutral-200 bg-neutral-0"
      )}
    >
      <div className="flex w-full items-center gap-3">
        <span
          className={cn(
            "flex size-[26px] shrink-0 items-center justify-center rounded-full text-xs leading-4 font-semibold text-neutral-0",
            top ? "bg-brand-700" : "bg-sidebar-active-bg"
          )}
        >
          {rank}
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
          <span className="text-sm leading-5 font-medium text-neutral-900">
            {provider.name}
          </span>
          <span className="flex flex-wrap items-center gap-[7px]">
            <span className="type-overline rounded-[5px] bg-neutral-100 px-[7px] py-0.5 text-neutral-600">
              {provider.kind.toUpperCase()}
            </span>
            <span className="text-xs leading-4 font-medium text-neutral-500">
              {provider.specialties.join(" · ")}
            </span>
          </span>
        </span>
        <span className="flex shrink-0 flex-col items-end gap-px">
          <span
            className={cn(
              "text-lg leading-[26px] font-semibold tracking-[-0.2px]",
              top ? "text-brand-800" : "text-neutral-800"
            )}
          >
            {provider.matchScore}
          </span>
          <span className="type-overline text-neutral-500">MATCH SCORE</span>
        </span>
      </div>

      <div className="flex w-full flex-wrap items-start gap-x-5 gap-y-2">
        <span className="flex items-center gap-[7px] text-xs leading-4 font-medium text-neutral-600">
          <MapPin className="size-[13px] shrink-0" strokeWidth={1.8} />
          {provider.address}
        </span>
        <span className="flex items-center gap-[7px] text-xs leading-4 font-medium text-neutral-600">
          <Move className="size-[13px] shrink-0" strokeWidth={1.8} />
          {provider.distanceKm} km away
        </span>
      </div>

      <div className="flex w-full flex-wrap items-start gap-x-5 gap-y-2">
        <span className="flex items-center gap-[7px] text-xs leading-4 font-medium text-neutral-600">
          {provider.phone ? (
            <Phone className="size-[13px] shrink-0" strokeWidth={1.8} />
          ) : (
            <PhoneOff className="size-[13px] shrink-0" strokeWidth={1.8} />
          )}
          {provider.phone ?? "Phone: Not available"}
        </span>
        <span className="flex items-center gap-[7px] text-xs leading-4 font-medium text-neutral-600">
          <Clock className="size-[13px] shrink-0" strokeWidth={1.8} />
          {provider.openingHours ?? "Opening hours: Not available"}
        </span>
      </div>

      <div className="flex w-full flex-wrap items-center justify-between gap-3 pt-0.5">
        <div className="flex items-center gap-[9px]">
          <span className="text-xs leading-4 font-medium text-neutral-500">
            Why ranked here
          </span>
          <span
            className="flex items-center gap-[3px]"
            title="Specialty relevance, distance, data completeness, other verified details"
          >
            {provider.matchBreakdown.map((width, index) => (
              <span
                key={index}
                className={cn("h-1.5 rounded-[3px]", BREAKDOWN_COLORS[index])}
                style={{ width }}
              />
            ))}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <a
            href={`https://www.openstreetmap.org/?mlat=${provider.coordinates.lat}&mlon=${provider.coordinates.lng}#map=17/${provider.coordinates.lat}/${provider.coordinates.lng}`}
            target="_blank"
            rel="noreferrer noopener"
            className="rounded-[7px] border border-neutral-300 bg-neutral-0 px-[13px] py-2 text-xs leading-4 font-semibold text-neutral-700 transition-colors hover:bg-neutral-50"
          >
            View on map
          </a>
          <a
            href={`https://www.openstreetmap.org/directions?to=${provider.coordinates.lat}%2C${provider.coordinates.lng}`}
            target="_blank"
            rel="noreferrer noopener"
            className="rounded-[7px] border border-neutral-300 bg-neutral-0 px-[13px] py-2 text-xs leading-4 font-semibold text-neutral-700 transition-colors hover:bg-neutral-50"
          >
            Directions
          </a>
        </div>
      </div>
    </article>
  );
}

function DetailRows({
  rows,
}: {
  rows: { label: string; value: string }[];
}) {
  return (
    <>
      {rows.map((row) => (
        <div key={row.label} className="flex w-full flex-wrap gap-3.5">
          <p className="w-[140px] shrink-0 text-xs leading-4 font-semibold text-neutral-600">
            {row.label}
          </p>
          <p className="min-w-[200px] flex-1 text-xs leading-4 font-medium text-neutral-700">
            {row.value}
          </p>
        </div>
      ))}
    </>
  );
}

export function ProviderResultsView({
  state,
  location,
  radiusKm,
}: {
  state: "results" | "empty" | "unavailable";
  location: string;
  radiusKm: number;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const availability = searchParams.get("availability") ?? "evenings";

  const availabilityLabel =
    availability === "this-week"
      ? "This week"
      : availability === "weekends"
        ? "Weekends"
        : availability === "flexible"
          ? "Flexible"
          : "Evenings";

  const criteria = [
    { label: "DETECTED ISSUE", value: "Potential allergy contradiction" },
    { label: "RECOMMENDED PROFESSIONAL", value: "Prescribing Doctor / Pharmacist" },
    { label: "YOUR LOCATION", value: `${location} · 9.6615 N, 80.0255 E` },
    { label: "AVAILABILITY PREFERENCE", value: availabilityLabel },
    { label: "SEARCH RADIUS", value: `${radiusKm} km` },
  ];

  function updateSearch(next: Record<string, string>) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(next)) params.set(key, value);
    router.push(`/providers/results?${params.toString()}`);
  }

  return (
    <div className="flex h-full w-full flex-col gap-3.5 px-4 py-[22px] md:px-[26px]">
      {/* search-criteria (35:1205) */}
      <div className="flex w-full flex-wrap gap-6 rounded-xl border border-brand-200 bg-sidebar-bg px-5 py-3.5">
        {criteria.map((item) => (
          <div key={item.label} className="flex min-w-[180px] flex-1 flex-col gap-1">
            <p className="type-overline text-sidebar-ink-dim">{item.label}</p>
            <p className="text-[13px] leading-[18px] font-medium text-sidebar-ink">
              {item.value}
            </p>
          </div>
        ))}
      </div>

      {/* columns (35:1221) */}
      <div className="flex w-full min-h-0 flex-1 flex-col gap-3.5 xl:flex-row xl:items-stretch">
        <section className="flex w-full min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-neutral-200 bg-neutral-0 shadow-card">
          <div className="flex flex-wrap items-center justify-between gap-2 px-[18px] py-3">
            <h2 className="text-base leading-6 font-semibold tracking-[-0.1px] text-neutral-900">
              {state === "results" ? "Ranked results" : "Search results"}
            </h2>
            <p className="text-xs leading-4 font-medium text-neutral-500">
              {state === "results"
                ? providerRankingWeights
                : state === "empty"
                  ? "0 providers returned"
                  : "Request failed"}
            </p>
          </div>
          <div className="h-px w-full bg-neutral-200" />

          <div className="scrollbar-thin flex min-h-0 flex-1 flex-col gap-[11px] overflow-y-auto px-4 py-3.5">
            {state === "results" && (
              <>
                {providers.map((provider, index) => (
                  <ProviderCard
                    key={provider.id}
                    provider={provider}
                    rank={index + 1}
                  />
                ))}
                <div className="flex w-full items-center gap-[9px] rounded-md bg-neutral-50 px-[13px] py-2.5">
                  <Info
                    className="size-3.5 shrink-0 text-neutral-500"
                    strokeWidth={1.8}
                  />
                  <p className="flex-1 text-xs leading-4 font-medium text-neutral-600">
                    {providerResultsNote}
                  </p>
                </div>
              </>
            )}

            {state === "empty" && (
              <>
                <div className="flex w-full flex-col items-center gap-4 px-6 pt-11 pb-[34px] text-center md:px-11">
                  <span className="flex size-16 items-center justify-center rounded-full bg-neutral-100">
                    <SearchX
                      className="size-[30px] text-neutral-500"
                      strokeWidth={1.8}
                    />
                  </span>
                  <h3 className="text-[22px] leading-[30px] font-semibold tracking-[-0.3px] text-neutral-900">
                    {providerEmptyState.headline}
                  </h3>
                  <p className="text-sm leading-[21px] text-neutral-600">
                    {providerEmptyState.body}
                  </p>
                  <div className="flex flex-wrap items-center justify-center gap-2.5 pt-1">
                    <Button
                      size="sm"
                      className="gap-[9px] px-[18px] py-[11px]"
                      onClick={() => updateSearch({ radius: "25", state: "results" })}
                    >
                      <Move className="size-[15px]" strokeWidth={1.8} />
                      Expand search area to 25 km
                    </Button>
                    <Button
                      render={<Link href="/providers" />}
                      variant="outline"
                      size="sm"
                      className="gap-[9px] px-[18px] py-[11px]"
                    >
                      <MapPinOff className="size-[15px]" strokeWidth={1.8} />
                      Change location
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="px-[18px] py-[11px]"
                      onClick={() =>
                        updateSearch({ availability: "flexible", state: "results" })
                      }
                    >
                      Remove availability filter
                    </Button>
                  </div>
                </div>
                <div className="h-px w-full bg-neutral-200" />
                <div className="flex w-full flex-col gap-[11px] rounded-[10px] bg-neutral-50 px-4 py-3.5">
                  <p className="type-overline text-neutral-500">WHAT WE SEARCHED</p>
                  <DetailRows rows={providerEmptyState.searchLog} />
                </div>
                <div className="flex w-full items-center gap-[9px] rounded-md bg-status-ok-bg px-[13px] py-[11px]">
                  <ShieldCheck
                    className="size-[15px] shrink-0 text-status-ok"
                    strokeWidth={1.8}
                  />
                  <p className="flex-1 text-xs leading-4 font-medium text-neutral-700">
                    {providerEmptyState.reassurance}
                  </p>
                </div>
              </>
            )}

            {state === "unavailable" && (
              <>
                <div className="flex w-full flex-col items-center gap-4 px-6 pt-11 pb-[34px] text-center md:px-11">
                  <span className="flex size-16 items-center justify-center rounded-full bg-risk-high-bg">
                    <TriangleAlert
                      className="size-[30px] text-risk-high"
                      strokeWidth={1.8}
                    />
                  </span>
                  <h3 className="text-[22px] leading-[30px] font-semibold tracking-[-0.3px] text-neutral-900">
                    {providerErrorState.headline}
                  </h3>
                  <p className="text-sm leading-[21px] text-neutral-600">
                    {providerErrorState.body}
                  </p>
                  <div className="flex flex-wrap items-center justify-center gap-2.5 pt-1">
                    <Button
                      size="sm"
                      className="gap-[9px] px-[18px] py-[11px]"
                      onClick={() => updateSearch({ state: "results" })}
                    >
                      <RefreshCw className="size-[15px]" strokeWidth={1.8} />
                      Try again
                    </Button>
                    <Button
                      render={<Link href="/findings" />}
                      variant="outline"
                      size="sm"
                      className="gap-[9px] px-[18px] py-[11px]"
                    >
                      <TriangleAlert className="size-[15px]" strokeWidth={1.8} />
                      Back to AI findings
                    </Button>
                  </div>
                </div>
                <div className="h-px w-full bg-neutral-200" />
                <div className="flex w-full flex-col gap-[11px] rounded-[10px] border border-neutral-200 bg-neutral-50 px-4 py-3.5">
                  <div className="flex items-center gap-[9px]">
                    <Info
                      className="size-3.5 shrink-0 text-neutral-500"
                      strokeWidth={1.8}
                    />
                    <p className="type-overline text-neutral-500">
                      TECHNICAL DETAIL
                    </p>
                  </div>
                  <DetailRows rows={providerErrorState.technical} />
                </div>
                <div className="flex w-full items-center gap-[9px] rounded-md bg-status-ok-bg px-[13px] py-[11px]">
                  <ShieldCheck
                    className="size-[15px] shrink-0 text-status-ok"
                    strokeWidth={1.8}
                  />
                  <p className="flex-1 text-xs leading-4 font-medium text-neutral-700">
                    {providerErrorState.reassurance}
                  </p>
                </div>
              </>
            )}
          </div>
        </section>

        <ProviderMap
          providers={state === "results" ? providers : []}
          locationLabel={location}
          unavailable={state === "unavailable"}
          className="min-h-[420px] w-full self-stretch xl:w-[452px] xl:shrink-0"
        />
      </div>
    </div>
  );
}
