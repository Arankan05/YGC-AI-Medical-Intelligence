import type { Metadata } from "next";
import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";

import { ProviderResultsView } from "./provider-results-view";

export const metadata: Metadata = {
  title: "Recommended healthcare providers — MediGuardian AI",
};

function firstValue(value: string | string[] | undefined): string | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  const trimmed = (raw ?? "").trim();
  return trimmed || undefined;
}

/**
 * Figma: 15 · Provider Results (35:1112).
 *
 * The results themselves are fetched in the client view, so no count can be
 * stated here — the subtitle describes the search that is running, not an
 * outcome that has not happened yet.
 */
export default async function ProviderResultsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;

  const location = firstValue(params.location);
  const latStr = firstValue(params.lat);
  const lngStr = firstValue(params.lng);
  const latitude = latStr !== undefined ? Number(latStr) : undefined;
  const longitude = lngStr !== undefined ? Number(lngStr) : undefined;
  const hasCoords = latitude !== undefined && !Number.isNaN(latitude) && longitude !== undefined && !Number.isNaN(longitude);

  const radiusKm = Number(firstValue(params.radius)) || 10;
  const availability = firstValue(params.availability);
  const specialty = firstValue(params.specialty);
  const findingId = firstValue(params.findingId);

  if (!location && !hasCoords) {
    return (
      <AppShell
        title="Recommended healthcare providers"
        subtitle="No location was provided"
      >
        <div className="flex min-h-full w-full flex-col items-center justify-center gap-4 px-6 py-16 text-center">
          <h2 className="text-[22px] leading-[30px] font-semibold tracking-[-0.3px] text-neutral-900">
            Tell us where to search
          </h2>
          <p className="max-w-md text-sm leading-[21px] text-neutral-600">
            Start from the provider search so we know which area to look in.
          </p>
          <a
            href="/providers"
            className="rounded-[9px] bg-brand-700 px-[18px] py-[11px] text-sm font-medium text-neutral-0 transition-colors hover:bg-brand-800"
          >
            Go to provider search
          </a>
        </div>
      </AppShell>
    );
  }

  const displayLocation = location || (hasCoords ? "Current Location" : "");

  return (
    <AppShell
      title="Recommended healthcare providers"
      subtitle={`Searching within ${radiusKm} km of ${displayLocation}`}
    >
      <Suspense fallback={null}>
        <ProviderResultsView
          location={location}
          latitude={hasCoords ? latitude : undefined}
          longitude={hasCoords ? longitude : undefined}
          radiusKm={radiusKm}
          availability={availability}
          specialty={specialty}
          findingId={findingId}
        />
      </Suspense>
    </AppShell>
  );
}
