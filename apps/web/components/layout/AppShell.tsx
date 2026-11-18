import type { ReactNode } from "react";

import AppHeader from "./AppHeader";
import AppNavigation from "./AppNavigation";
import AppFooter from "./AppFooter";

type AppShellProps = {
  children: ReactNode;
};

export default function AppShell({ children }: AppShellProps) {
  return (
    <>
      <a className="skip-link" href="#main">
        رفتن به محتوای اصلی
      </a>

      <div className="demo-bar">
        <span className="status-dot" />
        نسخهٔ آزمایشی محلی
        <span className="demo-detail">· تجربه‌های تألیفی برای امتحان‌کردن</span>
      </div>

      <AppHeader />

      {children}

      <AppNavigation />

      <AppFooter />
    </>
  );
}
