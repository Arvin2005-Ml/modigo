"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/hooks/useAuth";
import { paths } from "@/lib/navigation";

import Landing from "./Landing";

export default function LandingEntry() {
  const router = useRouter();
  const { status } = useAuth();

  const [legacyChecked, setLegacyChecked] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);

    const reset = params.get("reset_password");
    const slate = params.get("slate");
    const experience = params.get("experience");

    if (reset) {
      router.replace(`${paths.reset}?token=${encodeURIComponent(reset)}`);
      return;
    }

    if (experience) {
      router.replace(`/experiences/${encodeURIComponent(experience)}`);
      return;
    }

    if (slate) {
      router.replace(`${paths.results}?slate=${encodeURIComponent(slate)}`);
      return;
    }

    if (params.has("verify_email")) {
      router.replace(paths.login);
      return;
    }

    setLegacyChecked(true);
  }, [router]);

  useEffect(() => {
    if (legacyChecked && status === "authenticated") {
      router.replace(paths.discover);
    }
  }, [legacyChecked, status, router]);

  if (!legacyChecked || status !== "guest") {
    return (
      <main id="main" className="route-loading" role="status">
        در حال آماده‌سازی مودیگو…
      </main>
    );
  }

  return (
    <div className="landing-shell">
      <a className="skip-link" href="#main">
        رفتن به محتوای اصلی
      </a>

      <header className="landing-header">
        <Link href="/" aria-label="مودیگو، صفحهٔ اصلی">
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

          <Link href={paths.signup} className="landing-signup">
            ثبت‌نام
          </Link>
        </nav>
      </header>

      <main id="main" className="page-shell">
        <Landing
          start={() =>
            router.push(
              `${paths.login}?next=${encodeURIComponent(paths.questions)}`,
            )
          }
        />
      </main>

      <footer className="site-footer landing-footer">
        <span>مودیگو · با ریتم تو</span>

        <span>یه کم وقت برای خودت، بدون باید.</span>
      </footer>
    </div>
  );
}
