"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { useAuth } from "@/hooks/useAuth";
import { setAuthCookie } from "@/lib/auth/constants";
import { signUpWithEmail } from "@/lib/firebase/auth";
import { createUserDocument } from "@/lib/firebase/progress";
import { getAuthErrorMessage } from "@/lib/errors";

function SignupForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const lessonId = searchParams.get("lesson");
  const redirectTo = lessonId ? `/practice/${lessonId}` : "/onboarding";

  useEffect(() => {
    if (!loading && user) {
      router.replace(redirectTo);
    }
  }, [loading, user, router, redirectTo]);

  async function handleSignUp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setSubmitting(true);

    try {
      const result = await signUpWithEmail(email, password);
      await createUserDocument(result.user.uid, email, result.user.displayName);
      setAuthCookie(true);
      router.replace(redirectTo);
    } catch (err) {
      setError(getAuthErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading || user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
      </div>
    );
  }

  return (
    <AuthShell
      title="Sign up"
      subtitle="Create an account to start practicing"
      footer={
        <>
          Already have an account?{" "}
          <Link
            href={lessonId ? `/login?redirect=/practice/${lessonId}` : "/login"}
            className="text-emerald-400 hover:text-emerald-300"
          >
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSignUp} className="space-y-4">
        <div>
          <label
            htmlFor="email"
            className="mb-1.5 block font-mono text-xs text-zinc-400"
          >
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded border border-zinc-700 bg-[#0a0a0a] px-3 py-2 font-mono text-sm text-zinc-100 outline-none transition-colors placeholder:text-zinc-600 focus:border-emerald-500/60"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label
            htmlFor="password"
            className="mb-1.5 block font-mono text-xs text-zinc-400"
          >
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded border border-zinc-700 bg-[#0a0a0a] px-3 py-2 font-mono text-sm text-zinc-100 outline-none transition-colors placeholder:text-zinc-600 focus:border-emerald-500/60"
            placeholder="••••••••"
          />
        </div>

        <div>
          <label
            htmlFor="confirm-password"
            className="mb-1.5 block font-mono text-xs text-zinc-400"
          >
            Confirm password
          </label>
          <input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            required
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            className="w-full rounded border border-zinc-700 bg-[#0a0a0a] px-3 py-2 font-mono text-sm text-zinc-100 outline-none transition-colors placeholder:text-zinc-600 focus:border-emerald-500/60"
            placeholder="••••••••"
          />
        </div>

        {error ? (
          <p className="rounded border border-red-900/50 bg-red-950/30 px-3 py-2 font-mono text-xs text-red-400">
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded bg-emerald-600 px-4 py-2.5 font-mono text-sm font-medium text-black transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Creating account..." : "Create account"}
        </button>
      </form>
    </AuthShell>
  );
}

export default function SignupPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a]">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
        </div>
      }
    >
      <SignupForm />
    </Suspense>
  );
}