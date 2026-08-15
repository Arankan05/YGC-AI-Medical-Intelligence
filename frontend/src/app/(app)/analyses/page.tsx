import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { AnalysesView } from "./analyses-view";

export const metadata: Metadata = {
  title: "AI Analysis Logs — MediGuardian AI",
};

export default function AnalysesPage() {
  return (
    <AppShell
      title="AI Analysis"
      subtitle="Structured AI extraction logs and confidence telemetry"
    >
      <AnalysesView />
    </AppShell>
  );
}
