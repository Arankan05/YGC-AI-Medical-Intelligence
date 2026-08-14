import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { api } from "@/lib/api";

import { FindingDetailView } from "./finding-detail-view";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ findingId: string }>;
}): Promise<Metadata> {
  const { findingId } = await params;
  try {
    const finding = await api().getFinding(findingId);
    return { title: `${finding.title} — MediGuardian AI` };
  } catch {
    return { title: "Finding — MediGuardian AI" };
  }
}

/** Figma: 11 · Finding Detail (node 29:756). */
export default async function FindingDetailPage({
  params,
}: {
  params: Promise<{ findingId: string }>;
}) {
  const { findingId } = await params;
  try {
    const finding = await api().getFinding(findingId);
    if (!finding) notFound();

    return (
      <AppShell title="Finding detail" subtitle={`AI findings  ›  ${finding.title}`}>
        <FindingDetailView finding={finding} />
      </AppShell>
    );
  } catch {
    notFound();
  }
}
