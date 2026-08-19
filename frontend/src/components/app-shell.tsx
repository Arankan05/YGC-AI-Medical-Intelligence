"use client";

import { useRouter } from "next/navigation";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { Loader2 } from "lucide-react";

import { AppSidebar } from "@/components/app-sidebar";
import { AppTopBar } from "@/components/app-top-bar";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/supabase";
import type { Finding, UserProfile } from "@/lib/types";

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
  const [authStatus, setAuthStatus] = useState<"checking" | "authenticated" | "unauthenticated">("checking");
  const [notifications, setNotifications] = useState<Finding[]>([]);
  const [userProfile, setUserProfile] = useState<
    Pick<UserProfile, "fullName" | "initials" | "accountType">
  >({
    fullName: "Account",
    initials: "—",
    accountType: "Patient account",
  });

  useEffect(() => {
    let active = true;

    async function checkAuthAndLoad() {
      const token = await getAccessToken();
      if (!active) return;
      if (!token) {
        setAuthStatus("unauthenticated");
        router.replace("/sign-in");
        return;
      }

      setAuthStatus("authenticated");

      api()
        .getProfile()
        .then((profile) => {
          if (active) {
            setUserProfile({
              fullName: profile.fullName,
              initials: profile.initials,
              accountType: profile.accountType,
            });
          }
        })
        .catch(() => {
          if (active) {
            setAuthStatus("unauthenticated");
            router.replace("/sign-in");
          }
        });

      api()
        .listNotifications()
        .then((items) => {
          if (active) {
            setNotifications(items || []);
          }
        })
        .catch(() => {
          if (active) {
            setNotifications([]);
          }
        });
    }

    checkAuthAndLoad();

    return () => {
      active = false;
    };
  }, [router]);

  if (authStatus === "checking") {
    return (
      <div className="flex h-dvh w-full flex-col items-center justify-center gap-3 bg-neutral-50">
        <Loader2 className="size-7 animate-spin text-brand-700" />
        <p className="text-sm font-medium text-neutral-600">Verifying medical record workspace…</p>
      </div>
    );
  }

  if (authStatus === "unauthenticated") {
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
