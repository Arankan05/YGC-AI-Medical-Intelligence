import type { Metadata } from "next";
import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";

import { ProviderSearchForm } from "./provider-search-form";

export const metadata: Metadata = {
  title: "Find a healthcare provider — MediGuardian AI",
};

/** Figma: 14 · Provider Search Setup (node 33:1022). */
export default function ProvidersPage() {
  return (
    <AppShell
      title="Find a healthcare provider"
      subtitle="Triggered by a high-risk finding in your records"
    >
      {/* The form reads `findingId` from the query string, and useSearchParams
          must sit inside a Suspense boundary. */}
      <Suspense fallback={null}>
        <ProviderSearchForm />
      </Suspense>
    </AppShell>
  );
}
