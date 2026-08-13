import Link from "next/link";
import { ShieldAlert } from "lucide-react";

import { RiskBadge } from "@/components/risk-badge";
import { providerWhyCard } from "@/lib/data";

/** Figma: 14 · why-card (node 33:1115). */
export function ProviderWhyCard() {
  return (
    <div className="flex w-full flex-wrap items-center gap-3.5 rounded-xl border border-risk-high-border bg-risk-high-bg px-5 py-4">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-neutral-0">
        <ShieldAlert className="size-[19px] text-risk-high" strokeWidth={1.8} />
      </span>
      <div className="flex min-w-[260px] flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2.5">
          <h2 className="text-base leading-6 font-semibold tracking-[-0.1px] text-neutral-900">
            {providerWhyCard.title}
          </h2>
          <RiskBadge risk="high" />
        </div>
        <p className="text-[13px] leading-[19px] text-neutral-700">
          {providerWhyCard.body}
        </p>
      </div>
      <Link
        href={`/findings/${providerWhyCard.findingId}`}
        className="shrink-0 text-[13px] leading-[18px] font-medium text-risk-high hover:underline"
      >
        View finding &nbsp;→
      </Link>
    </div>
  );
}
