"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Loader2, LogOut, ShieldCheck } from "lucide-react";

import { BrandMark } from "@/components/brand-logo";
import { api } from "@/lib/api";
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
  const [signingOut, setSigningOut] = useState(false);

  async function handleSignOut() {
    if (signingOut) return;
    setSigningOut(true);
    try {
      await api().signOut();
    } catch (err) {
      console.error("Sign out error:", err);
    } finally {
      window.location.href = "/sign-in";
    }
  }

  return (
    <aside
      className={cn(
        "relative flex h-full w-[248px] shrink-0 flex-col gap-4 overflow-hidden border-r border-brand-200 px-3.5 pt-5 pb-4",
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

      <nav className="relative flex flex-1 flex-col gap-4 overflow-y-auto overflow-x-hidden scrollbar-thin pr-0.5">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="flex w-full flex-col gap-0.5">
            <p className="type-overline pb-1.5 pl-[11px] text-sidebar-ink-dim">
              {group.label}
            </p>
            {group.items.map((item) => {
              const active =
                pathname === item.href ||
                (item.href !== "/dashboard" && pathname.startsWith(`${item.href}/`));
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

      <div className="relative flex w-full items-start gap-[9px] rounded-[10px] bg-white/86 px-3 py-2.5">
        <ShieldCheck
          className="size-4 shrink-0 text-sidebar-ink"
          strokeWidth={1.8}
        />
        <p className="flex-1 text-[12px] leading-[17px] text-sidebar-ink">
          Informational only. This is not a medical diagnosis.
        </p>
      </div>

      <div className="relative flex w-full items-center justify-between gap-2 rounded-[10px] bg-white/82 p-2">
        <Link
          href="/profile"
          onClick={onNavigate}
          className="flex min-w-0 flex-1 items-center gap-2 rounded-md outline-none transition-colors hover:opacity-90 focus-visible:ring-3 focus-visible:ring-brand-700/25"
        >
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-sidebar-active-bg text-xs font-semibold text-sidebar-active-ink">
            {user.initials}
          </span>
          <span className="flex min-w-0 flex-1 flex-col gap-px">
            <span className="truncate text-[13px] font-medium text-sidebar-ink">
              {user.fullName}
            </span>
            <span className="truncate text-[11px] text-sidebar-ink-muted">
              {user.accountType}
            </span>
          </span>
        </Link>
        <button
          type="button"
          onClick={handleSignOut}
          disabled={signingOut}
          title="Sign out"
          aria-label="Sign out"
          className="flex size-8 shrink-0 items-center justify-center rounded-md border border-neutral-200/60 bg-white/80 text-neutral-600 transition-colors hover:border-risk-high-border hover:bg-risk-high-bg hover:text-risk-high"
        >
          {signingOut ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <LogOut className="size-4" strokeWidth={1.8} />
          )}
        </button>
      </div>
    </aside>
  );
}
