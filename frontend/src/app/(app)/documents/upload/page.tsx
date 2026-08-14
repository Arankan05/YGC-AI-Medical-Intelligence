import type { Metadata } from "next";
import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";
import { DocumentsView } from "../documents-view";
import { UploadModalRoute } from "./upload-modal-route";

export const metadata: Metadata = {
  title: "Upload documents — MediGuardian AI",
};

/** Figma: 05 · Upload & OCR Pipeline (node 24:310) — Documents with the upload modal open. */
export default function UploadPage() {
  return (
    <AppShell
      title="Documents"
      subtitle="View and manage your uploaded medical records"
    >
      <Suspense fallback={null}>
        <DocumentsView />
      </Suspense>
      <UploadModalRoute />
    </AppShell>
  );
}
