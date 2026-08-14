"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { UploadModal } from "@/components/upload-modal";
import { takeStagedUploads } from "@/lib/upload-store";

/** Keeps the upload modal on its own route so it is linkable and closes back to /documents. */
export function UploadModalRoute() {
  const router = useRouter();
  const [initialFiles] = useState(() => takeStagedUploads());
  const [open, setOpen] = useState(true);

  return (
    <UploadModal
      open={open}
      initialFiles={initialFiles}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          router.push("/documents");
          router.refresh();
        }
      }}
    />
  );
}
