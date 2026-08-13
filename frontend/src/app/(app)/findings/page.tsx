import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { recordTotals } from "@/lib/data";

import { FindingsView } from "./findings-view";

export const metadata: Metadata = {
  title: "AI findings — MediGuardian AI",
};

/** Figma: 10 · AI Findings (node 28:662). */
export default function FindingsPage() {
  return (
    <AppShell
      title="AI findings"
      subtitle={`${recordTotals.findings} potential issues detected across ${recordTotals.documents} documents · every finding links to its source`}
    >
      <FindingsView />
    </AppShell>
  );
}
