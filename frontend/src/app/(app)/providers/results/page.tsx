import type { Metadata } from "next";
import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";

import { ProviderResultsView } from "./provider-results-view";

export const metadata: Metadata = {
  title: "Recommended healthcare providers — MediGuardian AI",
};

/**
 * Figma: 15 · Provider Results (35:1112), plus its two states —
 * 16 · No Providers Found (37:1200) at `?state=empty` and
 * 17 · Provider Service Unavailable (37:1635) at `?state=unavailable`.
 */
export default async function ProviderResultsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const state =
    params.state === "empty" || params.state === "unavailable"
      ? params.state
      : "results";
  const location =
    typeof params.location === "string" && params.location.trim()
      ? params.location.trim()
      : "Jaffna";
  const radiusKm = Number(params.radius) || 10;

  const subtitle =
    state === "unavailable"
      ? "Provider lookup failed — your records are unaffected"
      : state === "empty"
        ? `No providers found within ${radiusKm} km of ${location}`
        : `4 real providers found within ${radiusKm} km of ${location}`;

  return (
    <AppShell title="Recommended healthcare providers" subtitle={subtitle}>
      <Suspense fallback={null}>
        <ProviderResultsView
          state={state}
          location={location}
          radiusKm={radiusKm}
        />
      </Suspense>
    </AppShell>
  );
}
