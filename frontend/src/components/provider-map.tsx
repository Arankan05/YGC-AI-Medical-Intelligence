"use client";

import { useEffect, useRef, useState } from "react";
import { CloudOff, Loader2 } from "lucide-react";
import type * as LType from "leaflet";

import { cn } from "@/lib/utils";
import type { Provider } from "@/lib/types";

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function ProviderMap({
  providers,
  origin = null,
  radiusKm = null,
  locationLabel,
  unavailable = false,
  selectedProviderId = null,
  onSelectProvider,
  className,
}: {
  providers: Provider[];
  /** Where the search location resolved to; markers cannot be placed without it. */
  origin?: { lat: number; lng: number } | null;
  radiusKm?: number | null;
  locationLabel: string;
  unavailable?: boolean;
  selectedProviderId?: string | null;
  onSelectProvider?: (providerId: string | null) => void;
  className?: string;
}) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<LType.Map | null>(null);
  const LRef = useRef<typeof LType | null>(null);
  const [leafletReady, setLeafletReady] = useState(false);

  const markersLayerRef = useRef<LType.LayerGroup | null>(null);
  const circleLayerRef = useRef<LType.Circle | null>(null);
  const originMarkerRef = useRef<LType.Marker | null>(null);
  const markerMapRef = useRef<Map<string, LType.Marker>>(new Map());

  const onSelectProviderRef = useRef(onSelectProvider);
  useEffect(() => {
    onSelectProviderRef.current = onSelectProvider;
  }, [onSelectProvider]);

  // Dynamically import Leaflet on client-side only (SSR safety)
  useEffect(() => {
    let isMounted = true;
    import("leaflet").then((mod) => {
      if (isMounted) {
        LRef.current = mod.default || mod;
        setLeafletReady(true);
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  // Initialize the Leaflet Map instance
  useEffect(() => {
    if (!leafletReady || !mapContainerRef.current || mapInstanceRef.current || unavailable) {
      return;
    }

    const L = LRef.current;
    if (!L) return;

    const map = L.map(mapContainerRef.current, {
      center: [0, 0],
      zoom: 13,
      zoomControl: true,
      attributionControl: false, // Custom attribution bar rendered below matching Figma
    });

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
    }).addTo(map);

    const markersLayer = L.layerGroup().addTo(map);
    markersLayerRef.current = markersLayer;
    mapInstanceRef.current = map;

    // Invalidate size in case container rendered in dynamic flex layout
    const timeoutId = setTimeout(() => {
      map.invalidateSize();
    }, 100);

    return () => {
      clearTimeout(timeoutId);
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
        markersLayerRef.current = null;
      }
    };
  }, [leafletReady, unavailable]);

  // Update map contents: search origin, radius circle, and provider markers
  useEffect(() => {
    const map = mapInstanceRef.current;
    const L = LRef.current;
    const markersLayer = markersLayerRef.current;

    if (!map || !L || !markersLayer || unavailable) {
      return;
    }

    // Clear previous layers
    markersLayer.clearLayers();
    markerMapRef.current.clear();

    if (circleLayerRef.current) {
      circleLayerRef.current.remove();
      circleLayerRef.current = null;
    }

    if (originMarkerRef.current) {
      originMarkerRef.current.remove();
      originMarkerRef.current = null;
    }

    // 1. Render Search Radius Circle and Origin Marker
    let radiusCircle: LType.Circle | null = null;
    if (origin) {
      const radiusMeters = Math.max((radiusKm || 10) * 1000, 100);
      radiusCircle = L.circle([origin.lat, origin.lng], {
        radius: radiusMeters,
        color: "#6544dc",
        weight: 2,
        dashArray: "6, 6",
        fillColor: "#7150e8",
        fillOpacity: 0.08,
      }).addTo(map);
      circleLayerRef.current = radiusCircle;

      const originIcon = L.divIcon({
        className: "custom-origin-pin !bg-transparent !border-none",
        html: `
          <div class="relative flex items-center justify-center size-6">
            <span class="absolute size-6 rounded-full bg-brand-500/30 animate-ping"></span>
            <span class="relative size-3.5 rounded-full bg-brand-700 border-2 border-white shadow-md"></span>
          </div>
        `,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });

      const originMarker = L.marker([origin.lat, origin.lng], {
        icon: originIcon,
        zIndexOffset: 100,
      })
        .bindPopup(`
          <div class="p-1 font-sans text-xs">
            <span class="font-bold text-neutral-900">Your Search Location</span>
            <div class="text-neutral-600">${escapeHtml(locationLabel)}</div>
            <div class="text-neutral-500 text-[11px] mt-0.5">Search radius: ${radiusKm || 10} km</div>
          </div>
        `)
        .addTo(map);
      originMarkerRef.current = originMarker;
    }

    // 2. Render Provider Markers
    const validProviders = providers
      .map((provider, index) => ({ provider, rank: index + 1 }))
      .filter(
        (item): item is { provider: Provider & { coordinates: { lat: number; lng: number } }; rank: number } =>
          item.provider.coordinates !== null &&
          typeof item.provider.coordinates.lat === "number" &&
          typeof item.provider.coordinates.lng === "number" &&
          !isNaN(item.provider.coordinates.lat) &&
          !isNaN(item.provider.coordinates.lng)
      );

    const boundsPoints: [number, number][] = [];
    if (origin) {
      boundsPoints.push([origin.lat, origin.lng]);
    }

    validProviders.forEach(({ provider, rank }) => {
      const isSelected = provider.id === selectedProviderId;
      const isTop = rank === 1;
      const lat = provider.coordinates.lat;
      const lng = provider.coordinates.lng;
      boundsPoints.push([lat, lng]);

      const bgStyle = isSelected
        ? "background-color: #42259c; box-shadow: 0 0 0 3px #c9c3f7, 0 4px 6px -1px rgba(0,0,0,0.1);"
        : isTop
          ? "background-color: #5634c4;"
          : "background-color: #6544dc;";

      const pointerBgStyle = isSelected
        ? "background-color: #42259c;"
        : isTop
          ? "background-color: #5634c4;"
          : "background-color: #6544dc;";

      const pinHtml = `
        <div class="relative flex flex-col items-center cursor-pointer group transition-transform ${
          isSelected ? "scale-115 -translate-y-1" : "hover:scale-105"
        }">
          <div class="flex size-[28px] items-center justify-center rounded-full border-2 border-white text-[12px] font-bold text-white shadow-md" style="${bgStyle}">
            ${rank}
          </div>
          <div class="-mt-1 size-2 rotate-45 border-r border-b border-white/40" style="${pointerBgStyle}"></div>
        </div>
      `;

      const customIcon = L.divIcon({
        className: "custom-provider-pin !bg-transparent !border-none",
        html: pinHtml,
        iconSize: [30, 36],
        iconAnchor: [15, 34],
        popupAnchor: [0, -32],
      });

      const marker = L.marker([lat, lng], {
        icon: customIcon,
        zIndexOffset: isSelected ? 1000 : 200 - rank,
        title: `${provider.name} (Rank #${rank})`,
      });

      const kindLabel = provider.kind ? provider.kind.toUpperCase() : "PROVIDER";
      const specialtiesText =
        provider.specialties && provider.specialties.length > 0
          ? escapeHtml(provider.specialties.join(" · "))
          : null;

      const popupHtml = `
        <div class="p-1 font-sans text-xs min-w-[210px] max-w-[270px]">
          <div class="flex items-start justify-between gap-1.5 mb-1.5">
            <div class="font-bold text-sm text-neutral-900 leading-snug">${escapeHtml(provider.name)}</div>
            <span class="shrink-0 rounded bg-neutral-100 px-1.5 py-0.5 text-[10px] font-semibold text-neutral-700">
              ${escapeHtml(kindLabel)}
            </span>
          </div>
          ${
            specialtiesText
              ? `<div class="text-neutral-600 text-[11px] mb-1">
                  <span class="font-semibold text-neutral-700">Specialty:</span> ${specialtiesText}
                </div>`
              : ""
          }
          <div class="text-neutral-600 text-[11px] mb-1">
            <span class="font-semibold text-neutral-700">Distance:</span> ${
              provider.distanceKm !== null ? `${provider.distanceKm.toFixed(1)} km away` : "Not available"
            }
          </div>
          ${
            provider.address
              ? `<div class="text-neutral-600 text-[11px] mb-1.5 line-clamp-2">
                  <span class="font-semibold text-neutral-700">Address:</span> ${escapeHtml(provider.address)}
                </div>`
              : ""
          }
          <div class="mt-2 pt-1.5 border-t border-neutral-200 flex items-center justify-between">
            <span class="text-[10px] uppercase font-semibold text-neutral-500">Match score</span>
            <span class="text-xs font-bold text-brand-800">${provider.matchScore}/100</span>
          </div>
        </div>
      `;

      marker.bindPopup(popupHtml, {
        autoPanPadding: [20, 20],
      });

      marker.on("click", () => {
        onSelectProviderRef.current?.(provider.id);
      });

      marker.addTo(markersLayer);
      markerMapRef.current.set(provider.id, marker);
    });

    // 3. Viewport Fitting
    if (validProviders.length > 0 && boundsPoints.length > 0) {
      const bounds = L.latLngBounds(boundsPoints);
      map.fitBounds(bounds, {
        padding: [40, 40],
        maxZoom: 16,
      });
    } else if (radiusCircle) {
      map.fitBounds(radiusCircle.getBounds(), {
        padding: [30, 30],
      });
    } else if (origin) {
      map.setView([origin.lat, origin.lng], 13);
    }
  }, [leafletReady, providers, origin, radiusKm, locationLabel, selectedProviderId, unavailable]);

  // Handle selected provider marker focus and popup
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !selectedProviderId) return;

    const marker = markerMapRef.current.get(selectedProviderId);
    if (marker) {
      marker.openPopup();
      map.flyTo(marker.getLatLng(), Math.max(map.getZoom(), 15), {
        duration: 0.6,
      });
    }
  }, [selectedProviderId]);

  return (
    <section
      className={cn(
        "flex w-full flex-col overflow-hidden rounded-xl border border-neutral-200 bg-neutral-0 shadow-card",
        className
      )}
    >
      {/* Map surface container */}
      <div
        data-map-surface
        className="relative min-h-[320px] flex-1 overflow-hidden bg-[#f2efe9]"
      >
        {unavailable ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-8 text-center bg-neutral-50">
            <span className="flex size-14 items-center justify-center rounded-full bg-neutral-100">
              <CloudOff className="size-6 text-neutral-500" strokeWidth={1.8} />
            </span>
            <p className="text-sm leading-[21px] font-medium text-neutral-600">
              Map unavailable while the provider service is not responding.
            </p>
          </div>
        ) : (
          <>
            {!leafletReady && (
              <div className="absolute inset-0 flex items-center justify-center bg-[#f2efe9] text-neutral-500 text-sm gap-2">
                <Loader2 className="size-5 animate-spin text-brand-700" />
                Loading map…
              </div>
            )}
            <div ref={mapContainerRef} className="h-full w-full min-h-[320px] z-0" />
          </>
        )}
      </div>

      {/* Attribution bar matching Figma design */}
      <div className="flex flex-wrap items-center justify-between gap-2 bg-neutral-50 px-3.5 py-2.5 border-t border-neutral-200 z-10">
        <span className="flex items-center gap-[7px]">
          <span className="size-2 rounded-full bg-brand-700" />
          <span className="text-xs leading-4 font-medium text-neutral-600">
            You · {locationLabel}
          </span>
        </span>
        <span className="text-xs leading-4 font-medium text-neutral-500">
          Leaflet · ©{" "}
          <a
            href="https://www.openstreetmap.org/copyright"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:underline text-neutral-600"
          >
            OpenStreetMap
          </a>{" "}
          contributors
        </span>
      </div>
    </section>
  );
}
