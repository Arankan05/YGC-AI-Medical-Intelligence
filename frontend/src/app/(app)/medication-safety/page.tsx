import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";

import { MedicationSafetyView } from "./medication-safety-view";

export const metadata: Metadata = {
  title: "Medication Safety — MediGuardian AI",
};

export default function MedicationSafetyPage() {
  return (
    <AppShell
      title="Medication Safety"
      subtitle="Deterministic checks for interactions, allergy contradictions, duplicates and dosage"
    >
      <MedicationSafetyView />
    </AppShell>
  );
}
