"use client";

import { useState } from "react";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/hooks/useAuth";

import {
  authModeFromPathname,
  paths,
  safeNextPath,
  type AuthMode,
} from "@/lib/navigation";

import Auth from "@/components/Auth";
import { Note } from "@/components/ui";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "یه مشکلی پیش اومد؛ دوباره امتحان کن.";
}

export default function AuthPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const { login, signup, forgotPassword, resetPassword } = useAuth();

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const mode = authModeFromPathname(pathname);

  const resetToken =
    pathname === paths.reset ? searchParams.get("token") : null;

  const next = safeNextPath(searchParams.get("next")) ?? paths.dashboard;

  const execute = async (action: () => Promise<void>): Promise<boolean> => {
    if (busy) return false;

    setBusy(true);
    setError("");

    try {
      await action();
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const handleModeChange = (nextMode: AuthMode) => {
    setError("");

    const destination =
      nextMode === "signup"
        ? paths.signup
        : nextMode === "forgot"
          ? paths.forgot
          : paths.login;

    const requestedNext = safeNextPath(searchParams.get("next"));

    router.push(
      requestedNext
        ? `${destination}?next=${encodeURIComponent(requestedNext)}`
        : destination,
    );
  };

  const handleLogin = (email: string, password: string) => {
    void execute(async () => {
      await login(email, password);
      router.replace(next);
    });
  };

  const handleSignup = (
    email: string,
    password: string,
    name: string,
  ): Promise<void> =>
    execute(async () => {
      await signup(email, password, name);
      router.replace(next);
    }).then(() => undefined);

  const handleForgot = (email: string): Promise<boolean> =>
    execute(async () => {
      await forgotPassword(email);
    });

  const handleReset = (password: string) => {
    if (!resetToken) {
      setError("لینک بازیابی رمز معتبر نیست.");
      return;
    }

    void execute(async () => {
      await resetPassword(resetToken, password);
    });
  };

  return (
    <main id="main" className="page-shell">
      {pathname === paths.login && searchParams.get("reset") === "success" && (
        <Note>رمز عبورت تغییر کرد. حالا می‌تونی با رمز جدید وارد بشی.</Note>
      )}

      {error && (
        <div className="error-banner" role="alert">
          <p>{error}</p>
        </div>
      )}

      <Auth
        mode={mode}
        onModeChange={handleModeChange}
        busy={busy}
        login={handleLogin}
        signup={handleSignup}
        forgot={handleForgot}
        reset={handleReset}
        resetToken={Boolean(resetToken)}
      />
    </main>
  );
}
