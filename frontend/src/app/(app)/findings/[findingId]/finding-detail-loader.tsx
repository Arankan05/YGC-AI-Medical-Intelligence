"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Loader2 } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { api, toErrorMessage } from "@/lib/api";
import type { Finding } from "@/lib/types";

import { FindingDetailView } from "./finding-detail-view";

/**
 * Loads a single finding through the authenticated browser API client.
 *
 * The Supabase session lives in the browser, so this request has to run on the
 * client: a server component cannot read the access token, and the backend
 * rejects the unauthenticated call with 401.
 */
export function FindingDetailLoader({ findingId }: { findingId: string }) {
  const [finding, setFinding] = useState<Finding | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadFinding = useCallback(() => {
    setLoading(true);
    setError(null);
    api()
      .getFinding(findingId)
      .then((data) => {
        setFinding(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(toErrorMessage(err));
        setLoading(false);
      });
  }, [findingId]);

  useEffect(() => {
    loadFinding();
  }, [loadFinding]);

  return (
    <AppShell
      title="Finding detail"
      subtitle={
        finding ? `AI findings  ›  ${finding.title}` : "AI findings  ›  Evidence"
      }
    >
      {loading && (
        <div className="flex min-h-full w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
          <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-neutral-200 bg-neutral-0 py-16 text-center shadow-card">
            <Loader2 className="size-5 animate-spin text-brand-600" />
            <p className="text-sm text-neutral-500">Loading finding...</p>
          </div>
        </div>
      )}

      {!loading && error && (
        <div className="flex min-h-full w-full flex-col gap-[18px] px-4 py-[22px] md:px-[26px]">
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-risk-high-border bg-risk-high-bg px-3.5 py-2.5 text-[13px] leading-[19px] text-risk-high"
          >
            <span>{error}</span>
            <Button
              size="sm"
              variant="outline"
              onClick={loadFinding}
              className="border-risk-high text-risk-high hover:bg-risk-high-bg"
            >
              Retry
            </Button>
          </div>
          <Link
            href="/findings"
            className="inline-flex items-center gap-1.5 text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
          >
            <ArrowLeft className="size-3.5" />
            Back to AI findings
          </Link>
        </div>
      )}

      {!loading && !error && finding && <FindingDetailView finding={finding} />}
    </AppShell>
  );
}
