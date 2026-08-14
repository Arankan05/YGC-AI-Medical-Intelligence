import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";

import { AskAiView } from "../ask-ai-view";

export const metadata: Metadata = {
  title: "Ask AI — no-diagnosis safety — MediGuardian AI",
};

/** Figma: 13 · Ask AI — No-Diagnosis Safety (node 32:934). */
export default function AskAiSafetyPage() {
  return (
    <AppShell
      title="Ask AI"
      subtitle="Safety behaviour · the assistant never claims or implies a diagnosis"
    >
      <AskAiView thread={[]} variant="safety" />
    </AppShell>
  );
}
