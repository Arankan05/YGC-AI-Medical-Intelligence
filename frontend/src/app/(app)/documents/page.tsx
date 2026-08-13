import type { Metadata } from "next";
import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";
import { recordTotals } from "@/lib/data";

import { DocumentsView } from "./documents-view";

export const metadata: Metadata = {
  title: "Documents — MediGuardian AI",
};

/** Figma: 04 · Documents (node 23:394). */
export default function DocumentsPage() {
  return (
    <AppShell
      title="Documents"
      subtitle={`${recordTotals.documents} documents from ${recordTotals.providers} providers · ${recordTotals.visits} visits`}
    >
      <Suspense fallback={null}>
        <DocumentsView />
      </Suspense>
    </AppShell>
  );
}
