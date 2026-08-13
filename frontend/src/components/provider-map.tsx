import { CloudOff } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Provider } from "@/lib/types";

/**
 * Figma: `panel · map` (node 35:1422).
 *
 * The panel renders the map surface, the search-radius ring, the "you are here"
 * dot and one numbered marker per ranked provider, plus the OpenStreetMap
 * attribution bar. Tiles themselves come from a Leaflet layer once the provider
 * service is connected — mount it inside the marked container below; the marker
 * layer already reads `provider.coordinates`.
 */
export function ProviderMap({
  providers,
  locationLabel,
  unavailable = false,
  className,
}: {
  providers: Provider[];
  locationLabel: string;
  unavailable?: boolean;
  className?: string;
}) {
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

            {providers.map((provider, index) => (
              <span
                key={provider.id}
                title={`${provider.name} · ${provider.distanceKm} km`}
                style={{
                  top: `${provider.mapPosition.top}%`,
                  left: `${provider.mapPosition.left}%`,
                }}
                className="absolute flex -translate-x-1/2 -translate-y-full flex-col items-center"
              >
                <span
                  className={cn(
                    "flex size-[26px] items-center justify-center rounded-full border-2 border-neutral-0 text-[11px] font-bold text-neutral-0 shadow-card",
                    index === 0 ? "bg-brand-700" : "bg-sidebar-active-bg"
                  )}
                >
                  {index + 1}
                </span>
                <span
                  className={cn(
                    "-mt-1 size-2 rotate-45",
                    index === 0 ? "bg-brand-700" : "bg-sidebar-active-bg"
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
