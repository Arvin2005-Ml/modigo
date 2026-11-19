import type { ReactNode } from "react";
import PublicShell from "@/components/layout/PublicShell";

export default function GuestLayout({ children }: { children: ReactNode }) {
  return <PublicShell>{children}</PublicShell>;
}
