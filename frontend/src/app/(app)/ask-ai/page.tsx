import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { chatHistory } from "@/lib/data";

import { AskAiView } from "./ask-ai-view";

export const metadata: Metadata = {
  title: "Ask AI — MediGuardian AI",
};

/** Figma: 12 · Ask AI (node 30:846). */
export default function AskAiPage() {
  return (
    <AppShell
      title="Ask AI"
      subtitle="Questions answered only from your own uploaded records"
    >
      <AskAiView thread={chatHistory} variant="default" />
    </AppShell>
  );
}
