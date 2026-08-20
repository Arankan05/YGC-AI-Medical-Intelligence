"use client";

import { useRouter } from "next/navigation";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { Loader2 } from "lucide-react";

import { AppSidebar } from "@/components/app-sidebar";
import { AppTopBar } from "@/components/app-top-bar";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useFindingsQuery, useProfileQuery } from "@/hooks/use-medical-data";
import { getAccessToken } from "@/lib/supabase";

/**
 * Figma: ⚙ Shell Template (node 23:134) — App Sidebar + App Top Bar + content.
 * Below `lg` the sidebar collapses into a sheet opened from the top bar.
 */
export function AppShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  const router = useRouter();
  const [navOpen, setNavOpen] = useState(false);
  const [authChecking, setAuthChecking] = useState(true);

  useEffect(() => {
    let active = true;
    getAccessToken().then((token) => {
      if (active) {
        if (!token) {
          router.replace("/sign-in");
        } else {
          setAuthChecking(false);
        }
      }
    });
    return () => {
      active = false;
    };
  }, [router]);

  const { data: profile, isError: profileError } = useProfileQuery(!authChecking);

  useEffect(() => {
    if (profileError) {
      router.replace("/sign-in");
    }
  }, [profileError, router]);

  const { data: findings = [] } = useFindingsQuery(profile?.id, Boolean(profile?.id));
  const notifications = findings.filter(
    (f) => f.risk === "high" || f.risk === "medium"
  );

  const userProfile = {
    fullName: profile?.fullName || "Account",
    initials: profile?.initials || "—",
    accountType: profile?.accountType || "Patient account",
  };

  if (authChecking || (!profile && !profileError)) {
    return (
      <div className="flex h-dvh w-full flex-col items-center justify-center gap-3 bg-neutral-50">
        <Loader2 className="size-7 animate-spin text-brand-700" />
        <p className="text-sm font-medium text-neutral-600">Verifying medical record workspace…</p>
      </div>
    );
  }

  if (profileError) {
    return null;
  }

  return (
    <div className="flex h-dvh w-full items-start overflow-hidden bg-neutral-50">
      <AppSidebar user={userProfile} className="hidden lg:flex" />

      <Sheet open={navOpen} onOpenChange={setNavOpen}>
        <SheetContent
          side="left"
          showCloseButton={false}
          className="w-[248px] gap-0 border-0 p-0 sm:max-w-[248px]"
        >
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <AppSidebar user={userProfile} onNavigate={() => setNavOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex h-full min-w-0 flex-1 flex-col">
        <Suspense
          fallback={
            <div className="h-[72px] w-full border-b border-neutral-200 bg-neutral-0" />
          }
        >
          <AppTopBar
            title={title}
            subtitle={subtitle}
            notifications={notifications}
            onOpenNav={() => setNavOpen(true)}
          />
        </Suspense>
        <main className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
