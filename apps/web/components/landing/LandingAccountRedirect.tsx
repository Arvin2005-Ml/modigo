"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import { paths } from "@/lib/navigation";
import { useAppSelector } from "@/lib/store/hooks";

export default function LandingAccountRedirect({ children }: { children: ReactNode }) {
  const router = useRouter();
  const authenticated = useAppSelector((state) => state.auth.status === "authenticated");

  useEffect(() => {
    if (authenticated) router.replace(paths.dashboard);
  }, [authenticated, router]);

  return authenticated ? (
    <main id="main" className="route-loading" role="status">
      در حال بازکردن حساب مودیگو…
    </main>
  ) : children;
}
