import type { ReactNode } from "react";

import { AuthBrandPanel } from "@/components/auth-brand-panel";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh w-full items-stretch bg-neutral-0">
      <AuthBrandPanel />
      <div className="relative flex min-w-0 flex-1 flex-col items-center justify-center bg-neutral-0 px-6 py-12">
        {children}
      </div>
    </div>
  );
}
