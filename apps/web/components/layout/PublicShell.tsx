import type { ReactNode } from "react";
import Image from "next/image";
import Link from "next/link";

import { paths } from "@/lib/navigation";

export default function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="landing-shell">
      <a className="skip-link" href="#main">رفتن به محتوای اصلی</a>
      <header className="landing-header">
        <Link href={paths.landing} aria-label="مودیگو، صفحهٔ اصلی">
          <Image
            src="/brand/moodigo-wordmark.png"
            alt="مودیگو"
            width={158}
            height={38}
            priority
            className="brand-wordmark"
          />
        </Link>
        <nav className="landing-nav" aria-label="ورود و ثبت‌نام">
          <Link href={paths.login}>ورود</Link>
          <Link href={paths.signup} className="landing-signup">ثبت‌نام</Link>
        </nav>
      </header>
      {children}
      <footer className="site-footer landing-footer">
        <span>مودیگو · با ریتم تو</span>
        <span>یه کم وقت برای خودت، بدون باید.</span>
      </footer>
    </div>
  );
}
