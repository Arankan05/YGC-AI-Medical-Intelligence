"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { AlertCircle, Mail } from "lucide-react";

import { Field, fieldInputClass } from "@/components/field";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { api, toErrorMessage } from "@/lib/api";
import { getAccessToken } from "@/lib/supabase";

type FieldErrors = {
  fullName?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
  acknowledged?: string;
};

/** Figma: 02 · Create Account — form-panel (node 15:112). */
export function SignUpForm() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [acknowledged, setAcknowledged] = useState(true);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmationNotice, setConfirmationNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    getAccessToken().then((token) => {
      if (active && token) {
        router.replace("/dashboard");
      }
    });
    return () => {
      active = false;
    };
  }, [router]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return;

    const nextErrors: FieldErrors = {};
    if (!fullName.trim()) nextErrors.fullName = "Enter your full name.";
    if (!email.trim()) nextErrors.email = "Enter your email address.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      nextErrors.email = "Enter a valid email address.";
    if (password.length < 8)
      nextErrors.password = "Use at least 8 characters.";
    if (confirmPassword !== password)
      nextErrors.confirmPassword = "Passwords do not match.";
    if (!acknowledged)
      nextErrors.acknowledged =
        "Please acknowledge that findings are informational only.";

    setErrors(nextErrors);
    setFormError(null);
    setConfirmationNotice(null);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      await api().signUp({
        fullName,
        email,
        password,
        acknowledgedDisclaimer: acknowledged,
      });
      router.push("/dashboard");
    } catch (error) {
      const msg = toErrorMessage(error);
      if (msg.toLowerCase().includes("confirm your account") || msg.toLowerCase().includes("check your email")) {
        setConfirmationNotice("Account created successfully! Please check your email inbox to confirm your account before signing in.");
      } else {
        setFormError(msg);
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (confirmationNotice) {
    return (
      <div className="flex w-full max-w-[380px] flex-col gap-5 rounded-xl border border-brand-200 bg-brand-50/50 p-6">
        <div className="flex size-12 items-center justify-center rounded-full bg-brand-100 text-brand-700">
          <Mail className="size-6" strokeWidth={1.8} />
        </div>
        <div className="flex flex-col gap-2">
          <h2 className="text-xl font-bold tracking-tight text-neutral-900">
            Check your email
          </h2>
          <p className="text-sm leading-6 text-neutral-600">
            {confirmationNotice}
          </p>
        </div>
        <Button render={<Link href="/sign-in" />} className="w-full">
          Return to Sign in
        </Button>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className="flex w-full max-w-[380px] flex-col gap-4"
    >
      <div className="flex w-full flex-col gap-[7px]">
        <h1 className="type-display text-neutral-900">Create your account</h1>
        <p className="text-[15px] leading-6 text-neutral-500">
          Your documents stay isolated to your account and are never shared with
          other users.
        </p>
      </div>

      <Field label="FULL NAME" htmlFor="fullName" error={errors.fullName}>
        <input
          id="fullName"
          name="fullName"
          autoComplete="name"
          placeholder="e.g. John Doe"
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          aria-invalid={Boolean(errors.fullName)}
          className={fieldInputClass}
        />
      </Field>

      <Field label="EMAIL ADDRESS" htmlFor="signup-email" error={errors.email}>
        <input
          id="signup-email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          aria-invalid={Boolean(errors.email)}
          className={fieldInputClass}
        />
      </Field>

      <Field label="PASSWORD" htmlFor="signup-password" error={errors.password}>
        <input
          id="signup-password"
          name="password"
          type="password"
          autoComplete="new-password"
          placeholder="At least 8 characters"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          aria-invalid={Boolean(errors.password)}
          className={fieldInputClass}
        />
      </Field>

      <Field
        label="CONFIRM PASSWORD"
        htmlFor="confirm-password"
        error={errors.confirmPassword}
      >
        <input
          id="confirm-password"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          placeholder="Re-enter your password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          aria-invalid={Boolean(errors.confirmPassword)}
          className={fieldInputClass}
        />
      </Field>

      <div className="flex w-full flex-col gap-1.5 pt-0.5">
        <label className="flex cursor-pointer items-start gap-2.5">
          <Checkbox
            checked={acknowledged}
            onCheckedChange={(checked) => setAcknowledged(checked === true)}
            className="mt-px size-[17px] rounded-[5px] data-[checked]:border-brand-700 data-[checked]:bg-brand-700"
          />
          <span className="flex-1 text-[13px] leading-[19px] text-neutral-600">
            I understand MediGuardian AI provides informational findings only and
            is not a medical diagnosis.
          </span>
        </label>
        {errors.acknowledged && (
          <p className="text-[13px] leading-[18px] text-risk-high">
            {errors.acknowledged}
          </p>
        )}
      </div>

      {formError && (
        <div
          role="alert"
          className="flex w-full items-start gap-2.5 rounded-lg border border-risk-high-border bg-risk-high-bg p-3.5 text-[13px] leading-[19px] text-risk-high"
        >
          <AlertCircle className="size-4 shrink-0 mt-0.5" strokeWidth={1.8} />
          <span className="flex-1 font-medium">{formError}</span>
        </div>
      )}

      <Button type="submit" size="lg" disabled={submitting} className="w-full">
        {submitting ? "Creating account…" : "Create account"}
      </Button>

      <p className="flex w-full items-center justify-center gap-[5px] text-[13px]">
        <span className="leading-[19px] text-neutral-500">
          Already have an account?
        </span>
        <Link
          href="/sign-in"
          className="leading-[18px] font-medium text-brand-700 hover:underline"
        >
          Sign in
        </Link>
      </p>
    </form>
  );
}
