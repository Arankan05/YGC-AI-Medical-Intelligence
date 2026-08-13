import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";

import { LabResultsView } from "./lab-results-view";

export const metadata: Metadata = {
  title: "Lab results & trends — MediGuardian AI",
};

/** Figma: 09 · Lab Results & Trends (node 27:574). */
export default function LabResultsPage() {
  return (
    <AppShell
      title="Lab results"
      subtitle="18 results from 3 lab reports · 4 tests with enough history to trend"
    >
      <LabResultsView />
    </AppShell>
  );
}
