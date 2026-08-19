import type { Metadata } from "next";

import { ResetPasswordForm } from "./reset-password-form";

export const metadata: Metadata = {
  title: "Update password — MediGuardian AI",
};

export default function ResetPasswordPage() {
  return <ResetPasswordForm />;
}
