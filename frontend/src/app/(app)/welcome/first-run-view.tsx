"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Activity, AlertTriangle, Lock, Upload } from "lucide-react";

import { MetricCard } from "@/components/metric-card";
import { Panel } from "@/components/panel";
import { UploadDropzone } from "@/components/upload-dropzone";
import { Button } from "@/components/ui/button";
import { emptyStateMetrics, gettingStartedSteps, currentUser } from "@/lib/data";
import { stageUploads } from "@/lib/upload-store";

const STEP_ICONS = {
  upload: Upload,
  activity: Activity,
  alert: AlertTriangle,
} as const;

export function FirstRunView() {
  const router = useRouter();

  function handleFiles(files: File[]) {
    stageUploads(files);
    router.push("/documents/upload");
  }

  return (
    <div className="flex min-h-full w-full flex-col gap-3.5 px-4 py-[22px] md:px-[26px]">
      {/* hero (39:1557) */}
      <div
        className="flex w-full flex-col items-center gap-6 rounded-[14px] px-[26px] py-6 md:flex-row"
        style={{
          backgroundImage:
            "linear-gradient(to right, #fdfdff 0%, #dfdcfa 55%, #a9b2e8 100%)",
        }}
      >
        <div className="flex min-w-0 flex-1 flex-col gap-[9px]">
          <h2 className="type-display text-sidebar-ink">
            Welcome, {currentUser.fullName}
          </h2>
          <p className="text-[15px] leading-6 text-sidebar-ink-muted">
            MediGuardian reads the medical documents you already have —
            prescriptions, lab reports, discharge summaries, doctor&rsquo;s notes
            — and looks for the things that do not line up between them. Nothing
            is analysed until you upload something.
          </p>
          <div className="flex flex-wrap items-center gap-2.5 pt-[5px]">
            <Button
              render={<Link href="/documents/upload" />}
              className="gap-[9px] rounded-[9px] bg-brand-600 px-[18px] py-3 hover:bg-brand-700"
            >
              <Upload className="size-4" strokeWidth={1.8} />
              Upload your first documents
            </Button>
            <Button
              render={<Link href="#how-it-works" />}
              variant="outline"
              className="rounded-[9px] border-sidebar-ink bg-transparent px-[18px] py-3 text-sidebar-ink-muted hover:bg-white/40"
            >
              See how it works
            </Button>
          </div>
        </div>
        <Image
          src="/brand/hero-art.svg"
          alt=""
          aria-hidden
          width={150}
          height={150}
          className="size-[150px] shrink-0"
        />
      </div>

      {/* getting-started (39:1578) */}
      <div
        id="how-it-works"
        className="grid w-full grid-cols-1 gap-3.5 md:grid-cols-3"
      >
        {gettingStartedSteps.map((step) => {
          const Icon = STEP_ICONS[step.icon];
          return (
            <div
              key={step.step}
              className="flex flex-col gap-[9px] rounded-xl border border-neutral-200 bg-neutral-0 px-[17px] pt-[15px] pb-4 shadow-card"
            >
              <div className="flex w-full items-center gap-[11px]">
                <span className="flex size-[34px] shrink-0 items-center justify-center rounded-[9px] bg-brand-50">
                  <Icon className="size-[17px] text-brand-700" strokeWidth={1.8} />
                </span>
                <span className="type-overline rounded-full bg-neutral-100 px-2 py-0.5 text-neutral-500">
                  {step.step}
                </span>
              </div>
              <p className="text-[15px] leading-6 text-neutral-900">
                {step.title}
              </p>
              <p className="text-[13px] leading-[19px] text-neutral-600">
                {step.description}
              </p>
            </div>
          );
        })}
      </div>

      {/* kpi-row (39:1610) */}
      <div className="grid w-full grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {emptyStateMetrics.map((metric) => (
          <MetricCard key={metric.id} metric={metric} muted />
        ))}
      </div>

      {/* panel · dropzone (39:1656) */}
      <Panel className="min-h-[380px] flex-1 p-[18px]">
        <UploadDropzone
          title="No documents yet"
          description="Drag files here, or browse to select them. You can add several at once — MediGuardian only starts finding contradictions once it has more than one document to compare."
          onFiles={handleFiles}
        />
        <div className="flex items-center gap-[9px] pt-4">
          <Lock className="size-3.5 shrink-0 text-neutral-500" strokeWidth={1.8} />
          <p className="text-xs leading-4 font-medium text-neutral-500">
            Your files are stored under your account only, and can be deleted
            permanently at any time from Profile &amp; security.
          </p>
        </div>
      </Panel>
    </div>
  );
}
