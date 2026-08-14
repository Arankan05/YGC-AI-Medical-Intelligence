"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Eye, EyeOff } from "lucide-react";

import { Field, fieldInputClass } from "@/components/field";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { api, toErrorMessage } from "@/lib/api";

/** Figma: 01 · Sign In — form-panel (node 15:43). */
export function SignInForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [keepSignedIn, setKeepSignedIn] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const nextErrors: typeof errors = {};
    if (!email.trim()) nextErrors.email = "Enter your email address.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      nextErrors.email = "Enter a valid email address.";
    if (!password) nextErrors.password = "Enter your password.";

    setErrors(nextErrors);
    setFormError(null);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      await api().signIn({ email, password, keepSignedIn });
      router.push("/dashboard");
    } catch (error) {
      setFormError(toErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className="flex w-full max-w-[380px] flex-col gap-[18px]"
    >
      <div className="flex w-full flex-col gap-[7px]">
        <h1 className="type-display text-neutral-900">Welcome back</h1>
        <p className="text-[15px] leading-6 text-neutral-500">
          Sign in to your secure medical record workspace.
        </p>
      </div>

      <Field label="EMAIL ADDRESS" htmlFor="email" error={errors.email}>
        <input
          id="email"
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

      <Field label="PASSWORD" htmlFor="password" error={errors.password}>
        <div className="relative w-full">
          <input
            id="password"
            name="password"
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            placeholder="••••••••••••"
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

      <div className="flex w-full items-center justify-between gap-3">
        <label className="flex cursor-pointer items-center gap-[9px]">
          <Checkbox
            checked={keepSignedIn}
            onCheckedChange={(checked) => setKeepSignedIn(checked === true)}
            className="size-[17px] rounded-[5px] data-[checked]:border-brand-700 data-[checked]:bg-brand-700"
          />
          <span className="text-[13px] leading-[19px] text-neutral-600">
            Keep me signed in
          </span>
        </label>
        <Link
          href="/sign-in"
          className="text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
        >
          Forgot password?
        </Link>
      </div>

      {formError && (
        <p
          role="alert"
          className="rounded-md border border-risk-high-border bg-risk-high-bg px-3.5 py-2.5 text-[13px] leading-[19px] text-risk-high"
        >
          {formError}
        </p>
      )}

      <Button type="submit" size="lg" disabled={submitting} className="w-full">
        {submitting ? "Signing in…" : "Sign in"}
      </Button>

      <p className="flex w-full items-center justify-center gap-[5px] text-[13px]">
        <span className="leading-[19px] text-neutral-500">
          New to MediGuardian?
        </span>
        <Link
          href="/sign-up"
          className="leading-[18px] font-medium text-brand-700 hover:underline"
        >
          Create an account
        </Link>
      </p>
    </form>
  );
}
