import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { findings } from "@/lib/data";

import { FindingDetailView } from "./finding-detail-view";

export function generateStaticParams() {
  return findings.map((finding) => ({ findingId: finding.id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ findingId: string }>;
}): Promise<Metadata> {
  const { findingId } = await params;
  const finding = findings.find((item) => item.id === findingId);
  return { title: `${finding?.title ?? "Finding"} — MediGuardian AI` };
}

/** Figma: 11 · Finding Detail (node 29:756). */
export default async function FindingDetailPage({
  params,
}: {
  params: Promise<{ findingId: string }>;
}) {
  const { findingId } = await params;
  const finding = findings.find((item) => item.id === findingId);
  if (!finding) notFound();

  return (
    <AppShell title="Finding detail" subtitle={`AI findings  ›  ${finding.title}`}>
      <FindingDetailView finding={finding} />
    </AppShell>
  );
}
