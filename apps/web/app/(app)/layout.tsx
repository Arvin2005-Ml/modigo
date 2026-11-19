import type { ReactNode } from "react";
import { Suspense } from "react";

import AppShell from "@/components/layout/AppShell";
import AuthRouteGuard from "@/components/auth/AuthRouteGuard";
import Funilo from "@/components/Funilo";
import StoreProvider from "../StoreProviders";

type Props = {
  children: ReactNode;
};

export default function ApplicationLayout({ children }: Props) {
  return (
    <StoreProvider>
      <AppShell>
        <Suspense
          fallback={
            <main id="main" className="route-loading" role="status">
              در حال آماده‌سازی مودیگو…
            </main>
          }
        >
          <AuthRouteGuard>
            <Funilo />
            {children}
          </AuthRouteGuard>
        </Suspense>
      </AppShell>
    </StoreProvider>
  );
}
