import type { Metadata } from "next";

import { SignInForm } from "./sign-in-form";

export const metadata: Metadata = {
  title: "Sign in — MediGuardian AI",
};

export default function SignInPage() {
  return <SignInForm />;
}
