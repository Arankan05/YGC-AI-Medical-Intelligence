import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";

import { MedicationsView } from "./medications-view";

export const metadata: Metadata = {
  title: "Medications & cross-check — MediGuardian AI",
};

/** Figma: 08 · Medications & Cross-Check (node 26:486). */
export default function MedicationsPage() {
  return (
    <AppShell
      title="Medications"
      subtitle="Review extracted medications and cross-document safety checks"
    >
      <MedicationsView />
    </AppShell>
  );
}
