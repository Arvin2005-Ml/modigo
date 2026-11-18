"use client";

import { useCallback, useEffect } from "react";

import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/hooks/useAuth";
import { paths } from "@/lib/navigation";

export function isUnauthorized(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    error.status === 401
  );
}

export function usePrivatePageAuth(returnTo: string) {
  const router = useRouter();

  const { user, status, expireSession: expire } = useAuth();

  const expireSession = useCallback(() => {
    expire(returnTo);
  }, [expire, returnTo]);

  useEffect(() => {
    if (status === "guest") {
      router.replace(`${paths.login}?next=${encodeURIComponent(returnTo)}`);
    }
  }, [status, returnTo, router]);

  return {
    user: status === "authenticated" ? user : null,

    redirecting: status === "checking" || status === "guest",

    authError: status === "unavailable",

    // The root bootstrap owns session recovery.
    retryAuth: () => window.location.reload(),

    expireSession,
  };
}
