"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { AlertCircle, CheckCircle2, Eye, EyeOff, KeyRound, Loader2 } from "lucide-react";

import { Field, fieldInputClass } from "@/components/field";
import { Button } from "@/components/ui/button";
import { api, toErrorMessage } from "@/lib/api";
import { getSupabase } from "@/lib/supabase";

type FieldErrors = {
  password?: string;
  confirmPassword?: string;
};

export function ResetPasswordForm() {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<"checking" | "valid" | "invalid">("checking");
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;

    async function verifyRecoverySession() {
      try {
        const sb = getSupabase();

        // Parse search params if available in browser
        const searchParams = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
        const code = searchParams?.get("code");
        const tokenHash = searchParams?.get("token_hash");
        const type = searchParams?.get("type");

        // 1. PKCE Code exchange flow
        if (code) {
          try {
            await sb.auth.exchangeCodeForSession(code);
          } catch {
            // Handled via onAuthStateChange or getSession recheck
          }
        }

        // 2. Token hash OTP verification flow
        if (tokenHash && type === "recovery") {
          try {
            await sb.auth.verifyOtp({ token_hash: tokenHash, type: "recovery" });
          } catch {
            // Handled via onAuthStateChange or getSession recheck
          }
        }

        // 3. Check existing session
        const { data: { session } } = await sb.auth.getSession();
        if (!active) return;

        if (session) {
          setSessionStatus("valid");
          return;
        }

        // Listen for auth state change (e.g. PASSWORD_RECOVERY event)
        const { data: authListener } = sb.auth.onAuthStateChange((event, eventSession) => {
          if (!active) return;
          if (event === "PASSWORD_RECOVERY" || eventSession) {
            setSessionStatus("valid");
          }
        });

        // 4. Brief fallback delay to allow Supabase JS SDK client hash/URL parsing
        setTimeout(async () => {
          if (!active) return;
          const { data: { session: recheck } } = await sb.auth.getSession();
          if (recheck) {
            setSessionStatus("valid");
          } else {
            setSessionStatus("invalid");
          }
        }, 1200);

        return () => {
          authListener.subscription.unsubscribe();
        };
      } catch {
        if (active) setSessionStatus("invalid");
      }
    }

    verifyRecoverySession();

    return () => {
      active = false;
    };
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return;

    const nextErrors: FieldErrors = {};
    if (password.length < 8) {
      nextErrors.password = "Use at least 8 characters.";
    }
    if (confirmPassword !== password) {
      nextErrors.confirmPassword = "Passwords do not match.";
    }

    setErrors(nextErrors);
    setFormError(null);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      await api().resetPassword(password);
      setSuccess(true);
    } catch (error) {
      setFormError(toErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  if (sessionStatus === "checking") {
    return (
      <div className="flex w-full max-w-[380px] flex-col items-center justify-center gap-3.5 rounded-xl border border-neutral-200 bg-neutral-0 p-8 shadow-sm">
        <Loader2 className="size-6 animate-spin text-brand-700" />
        <p className="text-sm font-medium text-neutral-600">Verifying password reset link…</p>
      </div>
    );
  }

  if (sessionStatus === "invalid") {
    return (
      <div className="flex w-full max-w-[380px] flex-col gap-5 rounded-xl border border-risk-high-border bg-risk-high-bg/50 p-6 shadow-sm">
        <div className="flex size-12 items-center justify-center rounded-full bg-risk-high-bg text-risk-high">
          <AlertCircle className="size-6" strokeWidth={1.8} />
        </div>
        <div className="flex flex-col gap-2">
          <h2 className="text-xl font-bold tracking-tight text-neutral-900">
            Invalid or expired link
          </h2>
          <p className="text-sm leading-6 text-neutral-600">
            Your password reset link is invalid or has expired. Please request a new password reset link to continue.
          </p>
        </div>
        <Button render={<Link href="/forgot-password" />} className="w-full">
          Request new password reset link
        </Button>
      </div>
    );
  }

  if (success) {
    return (
      <div className="flex w-full max-w-[380px] flex-col gap-5 rounded-xl border border-brand-200 bg-brand-50/50 p-6 shadow-sm">
        <div className="flex size-12 items-center justify-center rounded-full bg-brand-100 text-brand-700">
          <CheckCircle2 className="size-6" strokeWidth={1.8} />
        </div>
        <div className="flex flex-col gap-2">
          <h2 className="text-xl font-bold tracking-tight text-neutral-900">
            Password updated
          </h2>
          <p className="text-sm leading-6 text-neutral-600">
            Your password has been successfully updated. You can now sign in with your new credentials.
          </p>
        </div>
        <Button render={<Link href="/sign-in" />} className="w-full">
          Sign in to your account
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
        <h1 className="type-display text-neutral-900">Set new password</h1>
        <p className="text-[15px] leading-6 text-neutral-500">
          Enter your new password below.
        </p>
      </div>

      <Field label="NEW PASSWORD" htmlFor="new-password" error={errors.password}>
        <div className="relative w-full">
          <input
            id="new-password"
            name="password"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            placeholder="At least 8 characters"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-invalid={Boolean(errors.password)}
            className={`${fieldInputClass} pr-11`}
          />
          <button
            type="button"
            onClick={() => setShowPassword((value) => !value)}
            aria-label={showPassword ? "Hide password" : "Show password"}
            className="absolute top-1/2 right-3.5 -translate-y-1/2 text-neutral-500 transition-colors hover:text-neutral-700"
          >
            {showPassword ? (
              <EyeOff className="size-[17px]" strokeWidth={1.8} />
            ) : (
              <Eye className="size-[17px]" strokeWidth={1.8} />
            )}
          </button>
        </div>
      </Field>

      <Field
        label="CONFIRM NEW PASSWORD"
        htmlFor="confirm-new-password"
        error={errors.confirmPassword}
      >
        <input
          id="confirm-new-password"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          placeholder="Re-enter new password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          aria-invalid={Boolean(errors.confirmPassword)}
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
        {submitting ? "Updating password…" : "Update password"}
      </Button>

      <p className="flex w-full items-center justify-center gap-[5px] text-[13px]">
        <span className="leading-[19px] text-neutral-500">
          Back to
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
