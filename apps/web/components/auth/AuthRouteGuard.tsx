"use client";

import { useEffect, type ReactNode } from "react";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { isAuthPath, paths, safeNextPath } from "@/lib/navigation";

import { useAuth } from "@/lib/hooks/useAuth";

type Props = {
  children: ReactNode;
};

export default function AuthRouteGuard({ children }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const { user, status } = useAuth();

  const authPage = isAuthPath(pathname);
  const resetPage = pathname === paths.reset;

  const hasResetToken = Boolean(searchParams.get("token"));

  const isNormalAuthPage = authPage && !resetPage;

  const guestOnPrivatePage = status === "guest" && !authPage;

  const loggedInOnAuthPage = status === "authenticated" && isNormalAuthPage;

  const missingResetToken = resetPage && !hasResetToken;

  const forbiddenAdmin =
    status === "authenticated" &&
    pathname === paths.admin &&
    user?.role === "user";

  const shouldRedirect =
    guestOnPrivatePage ||
    loggedInOnAuthPage ||
    missingResetToken ||
    forbiddenAdmin;

  useEffect(() => {
    if (status === "checking" || status === "unavailable") {
      return;
    }

    if (missingResetToken) {
      router.replace(paths.login);
      return;
    }

    if (guestOnPrivatePage) {
      const query = searchParams.toString();

      const destination = pathname + (query ? `?${query}` : "");

      router.replace(`${paths.login}?next=${encodeURIComponent(destination)}`);

      return;
    }

    if (loggedInOnAuthPage) {
      const next = safeNextPath(searchParams.get("next"));

      router.replace(next ?? paths.discover);
      return;
    }

    if (forbiddenAdmin) {
      router.replace(paths.discover);
    }
  }, [
    router,
    pathname,
    searchParams,
    status,
    missingResetToken,
    guestOnPrivatePage,
    loggedInOnAuthPage,
    forbiddenAdmin,
  ]);

  if (shouldRedirect) {
    return (
      <main id="main" className="route-loading" role="status">
        در حال انتقال به صفحهٔ مناسب…
      </main>
    );
  }

  return <>{children}</>;
}
