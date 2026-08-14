import { Stethoscope } from "lucide-react";

/** Figma: 14 · why-card (node 33:1115). */
export function ProviderWhyCard() {
  return (
    <div className="flex w-full flex-wrap items-center gap-3.5 rounded-xl border border-brand-200 bg-brand-50 px-5 py-4">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-neutral-0">
        <Stethoscope className="size-[19px] text-brand-700" strokeWidth={1.8} />
      </span>
      <div className="flex min-w-[260px] flex-1 flex-col gap-1">
        <h2 className="text-base leading-6 font-semibold tracking-[-0.1px] text-neutral-900">
          Find Healthcare Specialists
        </h2>
        <p className="text-[13px] leading-[19px] text-neutral-700">
          Search verified medical practitioners and clinics near your location to review your records and consultations.
        </p>
      </div>
    </div>
  );
}
