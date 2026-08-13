import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";

import { ProfileView } from "./profile-view";

export const metadata: Metadata = {
  title: "Profile & security — MediGuardian AI",
};

/** Figma: 18 · Profile & Security (node 38:1376). */
export default function ProfilePage() {
  return (
    <AppShell
      title="Profile & security"
      subtitle="Your account, your records, and what happens to them"
    >
      <ProfileView />
    </AppShell>
  );
}
