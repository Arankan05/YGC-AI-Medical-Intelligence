import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { DocumentDetailView } from "./document-detail-view";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ documentId: string }>;
}): Promise<Metadata> {
  const { documentId } = await params;
  return {
    title: `Document ${documentId.slice(0, 8)} — MediGuardian AI`,
  };
}

export default async function DocumentDetailPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = await params;

  return (
    <AppShell
      title="Document detail"
      subtitle="Medical document intelligence and extracted entities"
    >
      <DocumentDetailView documentId={documentId} />
    </AppShell>
  );
}
