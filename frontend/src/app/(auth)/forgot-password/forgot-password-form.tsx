"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { AlertCircle, CheckCircle2, KeyRound } from "lucide-react";

import { Field, fieldInputClass } from "@/components/field";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return;

    if (!email.trim()) {
      setEmailError("Enter your email address.");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setEmailError("Enter a valid email address.");
      return;
    }

    setEmailError(null);
    setFormError(null);
    setSubmitting(true);

    try {
      await api().resetPasswordForEmail(email);
      setSubmitted(true);
    } catch {
      // Do not reveal whether email exists or network detail for privacy
      setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="flex w-full max-w-[380px] flex-col gap-5 rounded-xl border border-brand-200 bg-brand-50/50 p-6 shadow-sm">
        <div className="flex size-12 items-center justify-center rounded-full bg-brand-100 text-brand-700">
          <CheckCircle2 className="size-6" strokeWidth={1.8} />
        </div>
        <div className="flex flex-col gap-2">
          <h2 className="text-xl font-bold tracking-tight text-neutral-900">
            Check your email
          </h2>
          <p className="text-sm leading-6 text-neutral-600">
            If an account exists for <strong className="text-neutral-900">{email}</strong>, you will receive a password reset link shortly.
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
      className="flex w-full max-w-[380px] flex-col gap-[18px]"
    >
      <div className="flex w-full flex-col gap-[7px]">
        <h1 className="type-display text-neutral-900">Reset your password</h1>
        <p className="text-[15px] leading-6 text-neutral-500">
          Enter the email address associated with your MediGuardian account.
        </p>
      </div>

      <Field label="EMAIL ADDRESS" htmlFor="reset-email" error={emailError || undefined}>
        <input
          id="reset-email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          aria-invalid={Boolean(emailError)}
          className={fieldInputClass}
        />
      </Field>

      {formError && (
        <div
          role="alert"
          className="flex w-full items-start gap-2.5 rounded-lg border border-risk-high-border bg-risk-high-bg p-3.5 text-[13px] leading-[19px] text-risk-high"
        >
          <AlertCircle className="size-4 shrink-0 mt-0.5" strokeWidth={1.8} />
          <span className="flex-1 font-medium">{formError}</span>
        </div>
      )}

      <Button type="submit" size="lg" disabled={submitting} className="w-full gap-2">
        <KeyRound className="size-4" />
        {submitting ? "Sending reset link…" : "Send password reset link"}
      </Button>

      <p className="flex w-full items-center justify-center gap-[5px] text-[13px]">
        <span className="leading-[19px] text-neutral-500">
          Remember your password?
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
