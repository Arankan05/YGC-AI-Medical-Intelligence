import type { Metadata } from "next";

import { FindingDetailLoader } from "./finding-detail-loader";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ findingId: string }>;
}): Promise<Metadata> {
  const { findingId } = await params;
  return {
    title: `Finding ${findingId.slice(0, 8)} — MediGuardian AI`,
  };
}

/** Figma: 11 · Finding Detail (node 29:756). */
export default async function FindingDetailPage({
  params,
}: {
  params: Promise<{ findingId: string }>;
}) {
  const { findingId } = await params;

  return <FindingDetailLoader findingId={findingId} />;
}
