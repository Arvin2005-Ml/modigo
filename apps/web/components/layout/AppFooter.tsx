"use client";

import { usePathname } from "next/navigation";

import { paths } from "@/lib/navigation";
import { useAppSelector } from "@/lib/store/hooks";

export default function AppFooter() {
  const user = useAppSelector((state) => state.auth.user);
  const pathname = usePathname();
  const hasBottomNavigation = user && pathname !== paths.dashboard;

  return (
    <footer className={`site-footer ${hasBottomNavigation ? "with-navigation" : ""}`}>
      <span className="footer-brand">
        مودیگو
        <span>· با ریتم تو</span>
      </span>

      <span>یه کم وقت برای خودت، بدون باید.</span>

      <span className="footer-local">نسخهٔ آزمایشی</span>
    </footer>
  );
}
