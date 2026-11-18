import type { ReactNode } from "react";
import { Suspense } from "react";

import Funilo from "@/components/Funilo";

export default function ApplicationLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <>
      <Suspense
        fallback={
          <main className="route-loading">در حال آماده‌سازی مودیگو…</main>
        }
      >
        <Funilo />
      </Suspense>

      {children}
    </>
  );
}
