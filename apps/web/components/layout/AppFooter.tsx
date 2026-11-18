"use client";

import { useAppSelector } from "@/lib/store/hooks";

export default function AppFooter() {
  const user = useAppSelector((state) => state.auth.user);

  return (
    <footer className={`site-footer ${user ? "with-navigation" : ""}`}>
      <span className="footer-brand">
        مودیگو
        <span>· با ریتم تو</span>
      </span>

      <span>یه کم وقت برای خودت، بدون باید.</span>

      <span className="footer-local">نسخهٔ آزمایشی</span>
    </footer>
  );
}
