import Image from "next/image";
import { Activity, MapPin, Pill, ShieldCheck, type LucideIcon } from "lucide-react";

import { BrandMark } from "@/components/brand-logo";

const FEATURES: { icon: LucideIcon; title: string; description: string }[] = [
  {
    icon: Activity,
    title: "Unified patient timeline",
    description:
      "Labs, prescriptions and doctor notes from every visit merged in date order.",
  },
  {
    icon: Pill,
    title: "Prescription cross-checking",
    description:
      "Potential interactions, duplicates, dosage conflicts and allergy contradictions.",
  },
  {
    icon: MapPin,
    title: "Real nearby providers",
    description:
      "Clinics and specialists sourced from public OpenStreetMap data — never fabricated.",
  },
];

/** Figma: brand-panel shared by 01 · Sign In (15:3) and 02 · Create Account (15:72). */
export function AuthBrandPanel() {
  return (
    <div
      className="relative hidden h-full w-[560px] shrink-0 flex-col justify-between overflow-hidden p-[52px] lg:flex"
      style={{
        backgroundImage:
          "linear-gradient(117.66deg, #fdfdff 0%, #dfdcfa 39.007%, #a9b2e8 70.922%)",
      }}
    >
      <Image
        src="/brand/auth-decor.svg"
        alt=""
        aria-hidden
        fill
        className="pointer-events-none absolute inset-0 object-cover"
      />
      <Image
        src="/brand/logo-watermark.svg"
        alt=""
        aria-hidden
        width={556}
        height={556}
        className="pointer-events-none absolute top-[409.6px] left-[117.6px] size-[556px] max-w-none"
      />

      <div className="relative flex w-full flex-col gap-[34px]">
        <div className="flex items-center gap-[11px]">
          <BrandMark size={38} />
          <span className="text-lg leading-[26px] font-semibold tracking-[-0.2px] text-sidebar-ink">
            MediGuardian AI
          </span>
        </div>

        <div className="flex w-full flex-col gap-3.5">
          <h2 className="type-display text-sidebar-ink">
            Understand your medical records with{" "}
            <span className="text-brand-700">evidence,</span> not guesswork.
          </h2>
          <p className="text-[15px] leading-6 text-sidebar-ink-muted">
            Upload reports from every visit and provider. MediGuardian builds one
            timeline, cross-checks your prescriptions, and shows the evidence
            behind every finding.
          </p>
        </div>

        <ul className="flex w-full flex-col gap-[18px]">
          {FEATURES.map((feature) => {
            const Icon = feature.icon;
            return (
              <li key={feature.title} className="flex w-full items-start gap-3.5">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-brand-100">
                  <Icon
                    className="size-[19px] text-brand-700"
                    strokeWidth={1.8}
                  />
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
                  <span className="text-sm leading-5 font-medium text-sidebar-ink">
                    {feature.title}
                  </span>
                  <span className="text-[13px] leading-[19px] text-sidebar-ink-dim">
                    {feature.description}
                  </span>
                </span>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="relative flex w-full items-start gap-[11px] rounded-[10px] bg-brand-100 px-4 py-3.5">
        <ShieldCheck
          className="size-[17px] shrink-0 text-brand-700"
          strokeWidth={1.8}
        />
        <p className="flex-1 text-[13px] leading-[19px] text-sidebar-ink-muted">
          MediGuardian AI does not diagnose. It surfaces potential issues from
          your own records and recommends discussing them with a qualified
          healthcare professional.
        </p>
      </div>
    </div>
  );
}
