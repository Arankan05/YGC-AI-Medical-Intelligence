import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { AllergiesView } from "./allergies-view";

export const metadata: Metadata = {
  title: "Drug Allergies — MediGuardian AI",
};

export default function AllergiesPage() {
  return (
    <AppShell
      title="Allergies"
      subtitle="Recorded drug allergies and adverse reaction risks"
    >
      <AllergiesView />
    </AppShell>
  );
}
