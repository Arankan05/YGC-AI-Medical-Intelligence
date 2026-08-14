"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Field, fieldInputClass } from "@/components/field";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { api, ApiNotConfiguredError, toErrorMessage } from "@/lib/api";

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
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
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
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      await api().signUp({
        fullName,
        email,
        password,
        acknowledgedDisclaimer: acknowledged,
      });
      router.push("/welcome");
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
          placeholder="Ruwan Perera"
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
          placeholder="r.perera@example.lk"
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
        <p
          role="alert"
          className="rounded-md border border-risk-high-border bg-risk-high-bg px-3.5 py-2.5 text-[13px] leading-[19px] text-risk-high"
        >
          {formError}
        </p>
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
