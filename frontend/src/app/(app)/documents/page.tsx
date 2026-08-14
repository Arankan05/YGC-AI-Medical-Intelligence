import type { Metadata } from "next";
import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";
import { DocumentsView } from "./documents-view";

export const metadata: Metadata = {
  title: "Documents — MediGuardian AI",
};

/** Figma: 04 · Documents (node 23:394). */
export default function DocumentsPage() {
  return (
    <AppShell
      title="Documents"
      subtitle="View and manage your uploaded medical records"
    >
      <Suspense fallback={null}>
        <DocumentsView />
      </Suspense>
    </AppShell>
  );
}
