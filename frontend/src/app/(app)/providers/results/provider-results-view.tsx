"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Clock,
  Info,
  Loader2,
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
  LocationNotFoundError,
  ProviderDirectoryUnavailableError,
  api,
  toErrorMessage,
} from "@/lib/api";
import {
  providerEmptyState,
  providerErrorState,
  providerRankingWeights,
  providerResultsNote,
} from "@/lib/data";
import { cn } from "@/lib/utils";
import type { Provider, ProviderSearchResult } from "@/lib/types";

const BREAKDOWN_COLORS = [
  "bg-brand-700",
  "bg-brand-500",
  "bg-brand-200",
  "bg-neutral-300",
];

/** Scales a component's points to a bar width. The four sum to at most 100. */
const BREAKDOWN_PIXELS_PER_POINT = 1.4;

const KIND_LABELS: Record<string, string> = {
  hospital: "HOSPITAL",
  clinic: "CLINIC",
  doctor: "DOCTOR",
  pharmacy: "PHARMACY",
  laboratory: "LABORATORY",
};

const AVAILABILITY_LABELS: Record<string, string> = {
  "this-week": "This week",
  evenings: "Evenings",
  weekends: "Weekends",
  flexible: "Flexible",
};

/** What the search looked for, from the stored scope. */
function describeScope(kind: string, specialty: string | null): string {
  const label = KIND_LABELS[kind];
  if (!label) return "Healthcare provider";
  const readable = label.charAt(0) + label.slice(1).toLowerCase();
  if (!specialty) return readable;
  const titled = specialty.charAt(0).toUpperCase() + specialty.slice(1);
  return `${readable} · ${titled}`;
}

function ProviderCard({
  provider,
  rank,
  isSelected = false,
  onSelect,
}: {
  provider: Provider;
  rank: number;
  isSelected?: boolean;
  onSelect?: (id: string) => void;
}) {
  const top = rank === 1;
  const kindLabel = KIND_LABELS[provider.kind] ?? "PROVIDER";

  return (
    <article
      onClick={() => onSelect?.(provider.id)}
      className={cn(
        "flex w-full flex-col gap-2.5 rounded-[11px] border px-[15px] py-[13px] transition-all cursor-pointer",
        isSelected
          ? "border-brand-500 bg-brand-50/80 ring-2 ring-brand-600 shadow-sm"
          : top
            ? "border-brand-200 bg-brand-50 hover:border-brand-300"
            : "border-neutral-200 bg-neutral-0 hover:border-neutral-300 hover:bg-neutral-50/50"
      )}
    >
      <div className="flex w-full items-center gap-3">
        <span
          className={cn(
            "flex size-[26px] shrink-0 items-center justify-center rounded-full text-xs leading-4 font-semibold text-neutral-0 transition-colors",
            isSelected ? "bg-brand-800" : top ? "bg-brand-700" : "bg-sidebar-active-bg"
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
              {kindLabel}
            </span>
            <span className="text-xs leading-4 font-medium text-neutral-500">
              {/* Only specialties the source published are shown. */}
              {provider.specialties.length > 0
                ? provider.specialties.join(" · ")
                : "Specialty not published"}
            </span>
          </span>
        </span>
        <span className="flex shrink-0 flex-col items-end gap-px">
          <span
            className={cn(
              "text-lg leading-[26px] font-semibold tracking-[-0.2px]",
              isSelected ? "text-brand-900 font-bold" : top ? "text-brand-800" : "text-neutral-800"
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
          {provider.address ?? "Address: Not available"}
        </span>
        <span className="flex items-center gap-[7px] text-xs leading-4 font-medium text-neutral-600">
          <Move className="size-[13px] shrink-0" strokeWidth={1.8} />
          {provider.distanceKm !== null
            ? `${provider.distanceKm.toFixed(1)} km away`
            : "Distance: Not available"}
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
          {/* Published opening hours, verbatim — never an appointment slot. */}
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
            {provider.matchBreakdown.map((points, index) => (
              <span
                key={index}
                className={cn("h-1.5 rounded-[3px]", BREAKDOWN_COLORS[index])}
                style={{ width: Math.max(points * BREAKDOWN_PIXELS_PER_POINT, 2) }}
              />
            ))}
          </span>
        </div>
        {provider.coordinates && (
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onSelect?.(provider.id);
              }}
              className={cn(
                "rounded-[7px] border px-[13px] py-2 text-xs leading-4 font-semibold transition-colors",
                isSelected
                  ? "border-brand-600 bg-brand-700 text-white hover:bg-brand-800"
                  : "border-neutral-300 bg-neutral-0 text-neutral-700 hover:bg-neutral-50"
              )}
            >
              View on map
            </button>
            <a
              href={`https://www.openstreetmap.org/directions?to=${provider.coordinates.lat}%2C${provider.coordinates.lng}`}
              target="_blank"
              rel="noreferrer noopener"
              onClick={(e) => e.stopPropagation()}
              className="rounded-[7px] border border-neutral-300 bg-neutral-0 px-[13px] py-2 text-xs leading-4 font-semibold text-neutral-700 transition-colors hover:bg-neutral-50"
            >
              Directions
            </a>
          </div>
        )}
      </div>
    </article>
  );
}

function DetailRows({ rows }: { rows: { label: string; value: string }[] }) {
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

/**
 * `notFound` is deliberately separate from `empty`: a place name we could not
 * resolve is a different answer from a place with no providers in it, and
 * `unavailable` is different again — it means we could not look at all.
 */
type ViewState = "loading" | "results" | "empty" | "notFound" | "unavailable";

export function ProviderResultsView({
  location,
  latitude,
  longitude,
  radiusKm,
  availability,
  specialty,
  findingId,
}: {
  location?: string;
  latitude?: number;
  longitude?: number;
  radiusKm: number;
  availability?: string;
  specialty?: string;
  findingId?: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [state, setState] = useState<ViewState>("loading");
  const [result, setResult] = useState<ProviderSearchResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setState("loading");
    setErrorMessage(null);
    setSelectedProviderId(null);

    api()
      .searchProviders({
        location,
        latitude,
        longitude,
        radiusKm,
        availability,
        specialty,
        findingId,
      })
      .then((data) => {
        if (!active) return;
        setResult(data);
        setState(data.providers.length > 0 ? "results" : "empty");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setResult(null);
        if (error instanceof LocationNotFoundError) {
          setState("notFound");
        } else if (error instanceof ProviderDirectoryUnavailableError) {
          setState("unavailable");
        } else {
          setState("unavailable");
        }
        setErrorMessage(toErrorMessage(error));
      });

    return () => {
      active = false;
    };
  }, [location, latitude, longitude, radiusKm, availability, specialty, findingId]);

  const providers = result?.providers ?? [];

  const availabilityLabel = availability
    ? (AVAILABILITY_LABELS[availability] ?? availability)
    : "No preference";

  const displayLocation =
    location ||
    (latitude !== undefined && longitude !== undefined
      ? `Current Location (${latitude.toFixed(3)}°, ${longitude.toFixed(3)}°)`
      : "Current Location");

  const criteria = [
    {
      label: "SEARCH TARGET",
      value: result
        ? describeScope(result.scopeKind, result.scopeSpecialty)
        : describeScope(specialty ? "doctor" : "hospital", specialty ?? null),
    },
    { label: "LOCATION", value: displayLocation },
    { label: "AVAILABILITY PREFERENCE", value: availabilityLabel },
    { label: "SEARCH RADIUS", value: `${radiusKm} km` },
  ];

  function updateSearch(next: Record<string, string>) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(next)) {
      if (value) params.set(key, value);
      else params.delete(key);
    }
    router.push(`/providers/results?${params.toString()}`);
  }

  function retry() {
    router.refresh();
    setState("loading");
    setErrorMessage(null);
    setSelectedProviderId(null);
    api()
      .searchProviders({ location, latitude, longitude, radiusKm, availability, specialty, findingId })
      .then((data) => {
        setResult(data);
        setState(data.providers.length > 0 ? "results" : "empty");
      })
      .catch((error: unknown) => {
        setResult(null);
        setState(error instanceof LocationNotFoundError ? "notFound" : "unavailable");
        setErrorMessage(toErrorMessage(error));
      });
  }

  const headerNote =
    state === "loading"
      ? "Searching OpenStreetMap…"
      : state === "results"
        ? providerRankingWeights
        : state === "empty"
          ? "0 providers returned"
          : state === "notFound"
            ? "Location not recognised"
            : "Request failed";

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
              {headerNote}
            </p>
          </div>
          <div className="h-px w-full bg-neutral-200" />

          <div className="scrollbar-thin flex min-h-0 flex-1 flex-col gap-[11px] overflow-y-auto px-4 py-3.5">
            {state === "loading" && (
              <div
                role="status"
                aria-live="polite"
                className="flex w-full flex-col items-center gap-3 px-6 pt-16 pb-[34px] text-center"
              >
                <Loader2
                  className="size-7 animate-spin text-brand-700"
                  strokeWidth={1.8}
                />
                <p className="text-sm leading-[21px] text-neutral-600">
                  Finding healthcare providers near {location}…
                </p>
              </div>
            )}

            {state === "results" && (
              <>
                {providers.map((provider, index) => (
                  <ProviderCard
                    key={provider.id}
                    provider={provider}
                    rank={index + 1}
                    isSelected={selectedProviderId === provider.id}
                    onSelect={setSelectedProviderId}
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

            {(state === "empty" || state === "notFound") && (
              <>
                <div className="flex w-full flex-col items-center gap-4 px-6 pt-11 pb-[34px] text-center md:px-11">
                  <span className="flex size-16 items-center justify-center rounded-full bg-neutral-100">
                    {state === "notFound" ? (
                      <MapPinOff
                        className="size-[30px] text-neutral-500"
                        strokeWidth={1.8}
                      />
                    ) : (
                      <SearchX
                        className="size-[30px] text-neutral-500"
                        strokeWidth={1.8}
                      />
                    )}
                  </span>
                  <h3 className="text-[22px] leading-[30px] font-semibold tracking-[-0.3px] text-neutral-900">
                    {state === "notFound"
                      ? "We could not find that location"
                      : providerEmptyState.headline}
                  </h3>
                  <p className="text-sm leading-[21px] text-neutral-600">
                    {state === "notFound"
                      ? `“${location}” did not match any place we could search. Try a nearby town or a different spelling.`
                      : providerEmptyState.body}
                  </p>
                  <div className="flex flex-wrap items-center justify-center gap-2.5 pt-1">
                    {state === "empty" && radiusKm < 25 && (
                      <Button
                        size="sm"
                        className="gap-[9px] px-[18px] py-[11px]"
                        onClick={() => updateSearch({ radius: "25" })}
                      >
                        <Move className="size-[15px]" strokeWidth={1.8} />
                        Expand search area to 25 km
                      </Button>
                    )}
                    <Button
                      render={<Link href="/providers" />}
                      variant="outline"
                      size="sm"
                      className="gap-[9px] px-[18px] py-[11px]"
                    >
                      <MapPinOff className="size-[15px]" strokeWidth={1.8} />
                      Change location
                    </Button>
                    {state === "empty" && availability && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="px-[18px] py-[11px]"
                        onClick={() => updateSearch({ availability: "" })}
                      >
                        {/* Availability only ever influenced ranking, never
                            filtered — so this clears a preference, not a filter. */}
                        Clear time preference
                      </Button>
                    )}
                  </div>
                </div>
                {state === "empty" && (
                  <>
                    <div className="h-px w-full bg-neutral-200" />
                    <div className="flex w-full flex-col gap-[11px] rounded-[10px] bg-neutral-50 px-4 py-3.5">
                      <p className="type-overline text-neutral-500">
                        WHAT WE SEARCHED
                      </p>
                      <DetailRows
                        rows={[
                          {
                            label: "AREA SEARCHED",
                            value: `${radiusKm} km around ${location}`,
                          },
                          {
                            label: "SOURCE DATA",
                            value: "OpenStreetMap healthcare database",
                          },
                          {
                            label: "SPECIALTY FILTERS",
                            value: result
                              ? describeScope(result.scopeKind, result.scopeSpecialty)
                              : "Medical clinics and hospitals",
                          },
                        ]}
                      />
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
                      onClick={retry}
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
                  <DetailRows
                    rows={[
                      {
                        label: "ENDPOINT",
                        value: "Overpass API / Nominatim geocoder",
                      },
                      {
                        label: "STATUS",
                        value: errorMessage ?? "Service unreachable or timed out",
                      },
                    ]}
                  />
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
          origin={
            result?.origin ??
            (latitude !== undefined && longitude !== undefined
              ? { lat: latitude, lng: longitude }
              : null)
          }
          radiusKm={result?.radiusKm ?? radiusKm}
          locationLabel={displayLocation}
          unavailable={state === "unavailable"}
          selectedProviderId={selectedProviderId}
          onSelectProvider={setSelectedProviderId}
          className="min-h-[420px] w-full self-stretch xl:w-[452px] xl:shrink-0"
        />
      </div>
    </div>
  );
}
