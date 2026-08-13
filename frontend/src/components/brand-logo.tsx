import Image from "next/image";

import { cn } from "@/lib/utils";

/** Figma: logo mark used in the sidebar (34px) and the auth brand panel (38px). */
export function BrandMark({
  size = 34,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <span
      className={cn("inline-flex shrink-0 items-center justify-center", className)}
      style={{ width: size, height: size }}
    >
      <Image
        src="/brand/logo-mark.svg"
        alt="MediGuardian AI"
        width={size}
        height={size}
        priority
      />
    </span>
  );
}
