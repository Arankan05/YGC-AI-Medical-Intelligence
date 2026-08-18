"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Check, Info, Loader2, Locate, MapPin, Search, Stethoscope, TriangleAlert } from "lucide-react";

import { Panel, PanelHeader } from "@/components/panel";
import { ProviderAttribution } from "@/components/provider-attribution";
import { ProviderWhyCard } from "@/components/provider-why-card";
import { Button } from "@/components/ui/button";
import {
  availabilityOptions,
  providerSearchDefaults,
  providerSearchSteps,
  radiusOptions,
} from "@/lib/data";
import { cn } from "@/lib/utils";

export function ProviderSearchForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Carried through from a finding's "Find healthcare providers nearby" action,
  // so the search can derive a specialty and record what prompted it.
  const findingId = searchParams.get("findingId") ?? "";

  const [location, setLocation] = useState(providerSearchDefaults.location);
  const [coordinates, setCoordinates] = useState<{ lat: number; lng: number } | null>(null);
  const [geoLoading, setGeoLoading] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [availability, setAvailability] = useState(
    providerSearchDefaults.availability
  );
  const [radiusKm, setRadiusKm] = useState(providerSearchDefaults.radiusKm);
  const [error, setError] = useState<string | null>(null);

  function handleUseCurrentLocation() {
    if (typeof window === "undefined" || !("geolocation" in navigator)) {
      setGeoError("Geolocation is not supported by your browser.");
      return;
    }

    setGeoLoading(true);
    setGeoError(null);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        setCoordinates({ lat, lng });
        setLocation("Current Location");
        setGeoLoading(false);
        setError(null);
      },
      (err) => {
        setGeoLoading(false);
        if (err.code === err.PERMISSION_DENIED) {
          setGeoError(
            "Location permission was denied. Please allow location access in your browser or enter your city manually."
          );
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          setGeoError(
            "Location information is currently unavailable. Please enter a city or town manually."
          );
        } else if (err.code === err.TIMEOUT) {
          setGeoError(
            "Location request timed out. Please try again or enter your city manually."
          );
        } else {
          setGeoError(
            "Could not retrieve your current location. Please enter a location manually."
          );
        }
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000,
      }
    );
  }

  function handleLocationChange(value: string) {
    setLocation(value);
    if (coordinates) {
      setCoordinates(null);
    }
    if (geoError) {
      setGeoError(null);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!coordinates && !location.trim()) {
      setError("Enter a city, town or area so we can search near you.");
      return;
    }
    setError(null);
    const params = new URLSearchParams({
      radius: String(radiusKm),
      availability,
    });
    if (coordinates) {
      params.set("lat", coordinates.lat.toFixed(6));
      params.set("lng", coordinates.lng.toFixed(6));
      params.set("location", location.trim() || "Current Location");
    } else {
      params.set("location", location.trim());
    }
    if (findingId) params.set("findingId", findingId);
    router.push(`/providers/results?${params.toString()}`);
  }

  return (
    <div className="flex min-h-full w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
      <ProviderWhyCard />

      <form
        onSubmit={handleSubmit}
        className="flex w-full flex-1 flex-col gap-4 xl:flex-row xl:items-stretch"
      >
        {/* panel · Tell us where and when (33:1130) */}
        <Panel className="min-w-0 flex-1">
          <PanelHeader title="Tell us where and when" className="px-5 py-[13px]" />
          <div className="flex flex-col gap-[18px] px-5 pt-4 pb-[18px]">
            <div className="flex w-full flex-col gap-[9px]">
              <p className="text-xs leading-4 font-semibold text-neutral-700">
                {/* Only claim a match when a finding was actually carried in. */}
                {findingId
                  ? "SUITABLE PROFESSIONAL — MATCHED FROM THE FINDING"
                  : "SUITABLE PROFESSIONAL — GENERAL SEARCH"}
              </p>
              <div className="flex w-full flex-wrap items-center gap-[13px] rounded-[10px] border border-brand-200 bg-brand-50 px-4 py-3.5">
                <span className="flex size-[34px] shrink-0 items-center justify-center rounded-full bg-brand-700">
                  <Stethoscope
                    className="size-[17px] text-neutral-0"
                    strokeWidth={1.8}
                  />
                </span>
                <span className="flex min-w-[200px] flex-1 flex-col gap-[3px]">
                  <span className="text-sm leading-5 font-medium text-neutral-900">
                    {providerSearchDefaults.suitableProfessional.title}
                  </span>
                  <span className="text-[13px] leading-[19px] text-neutral-600">
                    {providerSearchDefaults.suitableProfessional.rationale}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={() => router.push("/findings")}
                  className="shrink-0 cursor-pointer text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
                >
                  Change
                </button>
              </div>
            </div>

            <div className="flex w-full flex-col gap-[9px]">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="location"
                  className="text-xs leading-4 font-semibold text-neutral-700"
                >
                  WHERE ARE YOU LOCATED?
                </label>
                <button
                  type="button"
                  onClick={handleUseCurrentLocation}
                  disabled={geoLoading}
                  className="flex cursor-pointer items-center gap-1.5 text-xs leading-4 font-medium text-brand-700 hover:text-brand-800 disabled:opacity-50"
                >
                  {geoLoading ? (
                    <>
                      <Loader2 className="size-3.5 animate-spin" />
                      <span>Locating…</span>
                    </>
                  ) : (
                    <>
                      <Locate className="size-3.5" strokeWidth={1.8} />
                      <span>Use my current location</span>
                    </>
                  )}
                </button>
              </div>
              <div className="flex h-[46px] w-full items-center gap-[11px] rounded-md border-[1.5px] border-brand-600 bg-neutral-0 px-[15px]">
                <MapPin
                  className="size-[17px] shrink-0 text-brand-700"
                  strokeWidth={1.8}
                />
                <input
                  id="location"
                  value={location}
                  onChange={(event) => handleLocationChange(event.target.value)}
                  placeholder="City, town or area"
                  className="w-full bg-transparent text-[15px] leading-6 text-neutral-900 outline-none placeholder:text-neutral-500"
                />
              </div>
              {coordinates && (
                <div className="flex items-center gap-2 rounded-md border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-medium text-brand-800">
                  <Locate className="size-3.5 shrink-0 text-brand-700" strokeWidth={1.8} />
                  <span>
                    Current location active ({coordinates.lat.toFixed(4)}°, {coordinates.lng.toFixed(4)}°)
                  </span>
                </div>
              )}
              {geoError && (
                <div className="flex items-start gap-2 rounded-md bg-risk-med-bg px-3 py-2 text-xs leading-4 text-risk-med">
                  <TriangleAlert className="mt-0.5 size-3.5 shrink-0" strokeWidth={1.8} />
                  <span className="flex-1">{geoError}</span>
                </div>
              )}
              <div className="flex w-full items-center gap-[9px] rounded-md bg-neutral-50 px-[13px] py-2.5">
                <Check
                  className="size-3.5 shrink-0 text-status-ok"
                  strokeWidth={2.2}
                />
                <p className="flex-1 text-xs leading-4 font-medium text-neutral-600">
                  {providerSearchDefaults.geocodeNote}
                </p>
              </div>
              {error && (
                <p role="alert" className="text-[13px] leading-[18px] text-risk-high">
                  {error}
                </p>
              )}
            </div>

            <div className="flex w-full flex-col gap-[9px]">
              <p className="text-xs leading-4 font-semibold text-neutral-700">
                WHEN ARE YOU AVAILABLE FOR CONSULTATION?
              </p>
              <div
                role="radiogroup"
                aria-label="Availability"
                className="grid w-full grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-4"
              >
                {availabilityOptions.map((option) => {
                  const selected = option.value === availability;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      onClick={() => setAvailability(option.value)}
                      className={cn(
                        "flex cursor-pointer items-center gap-2.5 rounded-[10px] px-3.5 py-3 text-left transition-colors",
                        selected
                          ? "border-[1.5px] border-brand-600 bg-brand-50"
                          : "border border-neutral-300 bg-neutral-0 hover:bg-neutral-50"
                      )}
                    >
                      <span
                        className={cn(
                          "flex size-[18px] shrink-0 items-center justify-center rounded-full",
                          selected
                            ? "bg-brand-600"
                            : "border-[1.5px] border-neutral-300 bg-neutral-0"
                        )}
                      >
                        {selected && (
                          <span className="size-1.5 rounded-full bg-neutral-0" />
                        )}
                      </span>
                      <span className="flex flex-col gap-0.5">
                        <span
                          className={cn(
                            "text-sm leading-5 font-medium",
                            selected ? "text-brand-800" : "text-neutral-800"
                          )}
                        >
                          {option.label}
                        </span>
                        <span className="text-xs leading-4 font-medium text-neutral-500">
                          {option.hint}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
              <div className="flex w-full items-center gap-[9px] rounded-md bg-risk-med-bg px-[13px] py-2.5">
                <TriangleAlert
                  className="size-3.5 shrink-0 text-risk-med"
                  strokeWidth={1.8}
                />
                <p className="flex-1 text-xs leading-4 font-medium text-neutral-700">
                  {providerSearchDefaults.availabilityNote}
                </p>
              </div>
            </div>

            <div className="flex w-full flex-col gap-[9px]">
              <p className="text-xs leading-4 font-semibold text-neutral-700">
                SEARCH RADIUS
              </p>
              <div className="flex flex-wrap gap-[9px]">
                {radiusOptions.map((option) => {
                  const selected = option === radiusKm;
                  return (
                    <button
                      key={option}
                      type="button"
                      aria-pressed={selected}
                      onClick={() => setRadiusKm(option)}
                      className={cn(
                        "cursor-pointer rounded-full px-[18px] py-[9px] text-[13px] leading-[18px] font-medium transition-colors",
                        selected
                          ? "bg-sidebar-active-bg text-sidebar-active-ink"
                          : "border border-neutral-300 bg-neutral-0 text-neutral-600 hover:bg-neutral-50"
                      )}
                    >
                      {option} km
                    </button>
                  );
                })}
              </div>
            </div>

            <Button
              type="submit"
              className="w-full gap-2.5 rounded-[9px] py-3.5 text-[15px] font-normal"
            >
              <Search className="size-[17px]" strokeWidth={1.8} />
              Find healthcare providers
            </Button>
          </div>
        </Panel>

        {/* side-column (33:1206) */}
        <aside className="flex w-full flex-col gap-3.5 xl:w-[340px] xl:shrink-0">
          <div className="flex w-full flex-col gap-[13px] rounded-xl border border-neutral-200 bg-neutral-0 px-4 py-[15px] shadow-card">
            <h2 className="text-base leading-6 font-semibold tracking-[-0.1px] text-neutral-900">
              How this search works
            </h2>
            {providerSearchSteps.map((step, index) => (
              <div key={step.title} className="flex w-full items-start gap-[11px]">
                <span className="flex size-[22px] shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs leading-4 font-semibold text-brand-800">
                  {index + 1}
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="text-[13px] leading-[18px] font-medium text-neutral-800">
                    {step.title}
                  </span>
                  <span className="text-xs leading-4 font-medium text-neutral-500">
                    {step.description}
                  </span>
                </span>
              </div>
            ))}
          </div>

          <ProviderAttribution className="flex-1" />
          <p className="flex items-start gap-2 text-xs leading-4 text-neutral-500">
            <Info className="size-3.5 shrink-0" strokeWidth={1.8} />
            Provider results come from the live OpenStreetMap Nominatim and
            Overpass services at the moment you search.
          </p>
        </aside>
      </form>
    </div>
  );
}
