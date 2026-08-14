import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";

import { TimelineView } from "./timeline-view";

export const metadata: Metadata = {
  title: "Patient timeline — MediGuardian AI",
};

/** Figma: 06 · Patient Timeline (node 25:398). */
export default function TimelinePage() {
  return (
    <AppShell
      title="Patient timeline"
      subtitle="Chronological record of your medical events"
    >
      <TimelineView />
    </AppShell>
  );
}
