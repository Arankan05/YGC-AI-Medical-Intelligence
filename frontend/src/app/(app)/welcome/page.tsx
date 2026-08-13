import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";

import { FirstRunView } from "./first-run-view";

export const metadata: Metadata = {
  title: "Get started — MediGuardian AI",
};

/** Figma: 03 · First Run — Empty State (node 39:1464). */
export default function WelcomePage() {
  return (
    <AppShell
      title="Dashboard"
      subtitle="Nothing here yet — add your first documents to begin"
    >
      <FirstRunView />
    </AppShell>
  );
}
