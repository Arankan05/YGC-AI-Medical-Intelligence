import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";

import { FindingsView } from "./findings-view";

export const metadata: Metadata = {
  title: "AI findings — MediGuardian AI",
};

/** Figma: 10 · AI Findings (node 28:662). */
export default function FindingsPage() {
  return (
    <AppShell
      title="AI findings"
      subtitle="Potential cross-document contradictions and safety alerts"
    >
      <FindingsView />
    </AppShell>
  );
}
