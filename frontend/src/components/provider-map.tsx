import { CloudOff } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Provider } from "@/lib/types";

/**
 * Figma: `panel · map` (node 35:1422).
 *
 * The panel renders the map surface, the search-radius ring, the "you are here"
 * dot and one numbered marker per ranked provider, plus the OpenStreetMap
 * attribution bar. Tiles themselves come from a Leaflet layer — mount it inside
 * the marked container below; the marker layer reads `provider.coordinates`.
 *
 * Marker placement is derived here rather than stored: the backend returns
 * latitude and longitude, and where that falls on this panel is purely a
 * presentation concern.
 */

/** The dashed radius ring is `w-[62%]`, so its radius is 31% of the box. */
const RING_RADIUS_PERCENT = 31;

/** Rough kilometres per degree of latitude; good enough at city scale. */
const KM_PER_DEGREE = 111.32;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

/**
 * Projects a provider onto the panel, in percent of the box.
 *
 * An equirectangular projection scaled so the search radius lands on the ring.
 * The panel is not square, so a point at exactly the radius sits on the ring
 * horizontally and near it vertically — this is a locator, not a survey map.
 * Markers are clamped inside the panel so one just beyond the radius stays
 * visible at the edge instead of being clipped away.
 */
function projectToPanel(
  origin: { lat: number; lng: number },
  point: { lat: number; lng: number },
  radiusKm: number
) {
  const eastKm =
    (point.lng - origin.lng) *
    KM_PER_DEGREE *
    Math.cos((origin.lat * Math.PI) / 180);
  const northKm = (point.lat - origin.lat) * KM_PER_DEGREE;
  const scale = RING_RADIUS_PERCENT / Math.max(radiusKm, 0.1);

  return {
    left: clamp(50 + eastKm * scale, 6, 94),
    top: clamp(50 - northKm * scale, 8, 92),
  };
}

export function ProviderMap({
  providers,
  origin = null,
  radiusKm = null,
  locationLabel,
  unavailable = false,
  className,
}: {
  providers: Provider[];
  /** Where the search location resolved to; markers cannot be placed without it. */
  origin?: { lat: number; lng: number } | null;
  radiusKm?: number | null;
  locationLabel: string;
  unavailable?: boolean;
  className?: string;
}) {
  // A provider the source gave no coordinates for cannot be placed. It stays in
  // the ranked list and is simply absent from the map, rather than being
  // dropped somewhere plausible.
  const plotted =
    origin && radiusKm
      ? providers.flatMap((provider, index) =>
          provider.coordinates
            ? [
                {
                  provider,
                  rank: index + 1,
                  position: projectToPanel(origin, provider.coordinates, radiusKm),
                },
              ]
            : []
        )
      : [];

  return (
    <section
      className={cn(
        "flex w-full flex-col overflow-hidden rounded-xl border border-neutral-200 bg-neutral-0 shadow-card",
        className
      )}
    >
      {/* map surface — Leaflet tile layer mounts here */}
      <div
        data-map-surface
        className="relative min-h-[320px] flex-1 overflow-hidden bg-[#f2efe9]"
      >
        {unavailable ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-8 text-center">
            <span className="flex size-14 items-center justify-center rounded-full bg-neutral-100">
              <CloudOff className="size-6 text-neutral-500" strokeWidth={1.8} />
            </span>
            <p className="text-sm leading-[21px] font-medium text-neutral-600">
              Map unavailable while the provider service is not responding.
            </p>
          </div>
        ) : (
          <>
            {/* search radius ring around the patient's location */}
            <span className="absolute top-1/2 left-1/2 aspect-square w-[62%] -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-dashed border-brand-600/60 bg-brand-500/10" />
            {/* you are here */}
            <span className="absolute top-1/2 left-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-neutral-0 bg-brand-700 shadow-card" />

            {plotted.map(({ provider, rank, position }) => (
              <span
                key={provider.id}
                title={
                  provider.distanceKm !== null
                    ? `${provider.name} · ${provider.distanceKm.toFixed(1)} km`
                    : provider.name
                }
                style={{ top: `${position.top}%`, left: `${position.left}%` }}
                className="absolute flex -translate-x-1/2 -translate-y-full flex-col items-center"
              >
                <span
                  className={cn(
                    "flex size-[26px] items-center justify-center rounded-full border-2 border-neutral-0 text-[11px] font-bold text-neutral-0 shadow-card",
                    rank === 1 ? "bg-brand-700" : "bg-sidebar-active-bg"
                  )}
                >
                  {rank}
                </span>
                <span
                  className={cn(
                    "-mt-1 size-2 rotate-45",
                    rank === 1 ? "bg-brand-700" : "bg-sidebar-active-bg"
                  )}
                />
              </span>
            ))}
          </>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 bg-neutral-50 px-3.5 py-2.5">
        <span className="flex items-center gap-[7px]">
          <span className="size-2 rounded-full bg-brand-700" />
          <span className="text-xs leading-4 font-medium text-neutral-600">
            You · {locationLabel}
          </span>
        </span>
        <span className="text-xs leading-4 font-medium text-neutral-500">
          Leaflet · © OpenStreetMap contributors
        </span>
      </div>
    </section>
  );
}
