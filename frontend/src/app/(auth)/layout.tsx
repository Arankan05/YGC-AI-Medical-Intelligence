import type { ReactNode } from "react";

import { AuthBrandPanel } from "@/components/auth-brand-panel";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh w-full items-stretch overflow-x-hidden bg-neutral-0">
      <AuthBrandPanel />
      <div className="relative flex min-h-dvh min-w-0 flex-1 flex-col items-center justify-center bg-neutral-0 px-4 py-8 md:px-6 md:py-12">
        {children}
      </div>
    </div>
  );
}
