"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck } from "lucide-react";

import { BrandMark } from "@/components/brand-logo";
import { NAV_GROUPS } from "@/lib/navigation";
import { cn } from "@/lib/utils";
import type { UserProfile } from "@/lib/types";

/**
 * Figma: App Sidebar (node 12:2)
 * Global navigation shell. The active page gets the brand fill + white ink.
 */
export function AppSidebar({
  user,
  onNavigate,
  className,
}: {
  user: Pick<UserProfile, "fullName" | "initials" | "accountType">;
  onNavigate?: () => void;
  className?: string;
}) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "relative flex h-full w-[248px] shrink-0 flex-col gap-[22px] overflow-hidden border-r border-brand-200 px-3.5 pt-5 pb-4",
        className
      )}
      style={{
        backgroundImage:
          "linear-gradient(to bottom, #ffffff 0%, #efedfd 42%, #6e7fcb 100%)",
      }}
    >
      <Image
        src="/brand/sidebar-decor.svg"
        alt=""
        aria-hidden
        fill
        className="pointer-events-none absolute inset-0 object-cover"
      />
      <Image
        src="/brand/sidebar-watermark.svg"
        alt=""
        aria-hidden
        width={358}
        height={358}
        className="pointer-events-none absolute -left-2 top-[486px] size-[358px] max-w-none"
      />

      <Link
        href="/dashboard"
        onClick={onNavigate}
        className="relative flex w-full items-center gap-2.5 rounded-lg outline-none focus-visible:ring-3 focus-visible:ring-brand-700/25"
      >
        <BrandMark size={34} />
        <span className="flex flex-col gap-px">
          <span className="text-base leading-6 font-semibold tracking-[-0.1px] text-sidebar-ink">
            MediGuardian
          </span>
          <span className="type-overline text-sidebar-ink-muted">
            Medical Record Intelligence
          </span>
        </span>
      </Link>

      <nav className="relative flex flex-col gap-[22px]">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="flex w-full flex-col gap-0.5">
            <p className="type-overline pb-2 pl-[11px] text-sidebar-ink-dim">
              {group.label}
            </p>
            {group.items.map((item) => {
              const active =
                pathname === item.href || pathname.startsWith(`${item.href}/`);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex w-full items-center gap-[11px] rounded-[9px] px-[11px] py-[9px] text-sm leading-5 font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-brand-700/25",
                    active
                      ? "bg-sidebar-active-bg text-sidebar-active-ink"
                      : "text-sidebar-ink-muted hover:bg-white/55"
                  )}
                >
                  <Icon className="size-[18px] shrink-0" strokeWidth={1.8} />
                  <span className="truncate">{item.label}</span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="relative flex-1" />

      <div className="relative flex w-full items-start gap-[9px] rounded-[10px] bg-white/86 px-3 py-[11px]">
        <ShieldCheck
          className="size-4 shrink-0 text-sidebar-ink"
          strokeWidth={1.8}
        />
        <p className="flex-1 text-[13px] leading-[19px] text-sidebar-ink">
          Informational only. This is not a medical diagnosis.
        </p>
      </div>

      <Link
        href="/profile"
        onClick={onNavigate}
        className="relative flex w-full items-center gap-2.5 rounded-[10px] bg-white/82 px-3 py-2.5 outline-none transition-colors hover:bg-white focus-visible:ring-3 focus-visible:ring-brand-700/25"
      >
        <span className="flex size-[34px] shrink-0 items-center justify-center rounded-full bg-sidebar-active-bg text-xs leading-4 font-semibold text-sidebar-active-ink">
          {user.initials}
        </span>
        <span className="flex flex-col gap-px">
          <span className="text-[13px] leading-[18px] font-medium text-sidebar-ink">
            {user.fullName}
          </span>
          <span className="text-xs leading-4 font-medium text-sidebar-ink-muted">
            {user.accountType}
          </span>
        </span>
      </Link>
    </aside>
  );
}
