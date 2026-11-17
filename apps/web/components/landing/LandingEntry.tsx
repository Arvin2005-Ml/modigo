"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { apiSlice } from "@/lib/store/api/apiSlice";
import { useAppDispatch } from "@/lib/store/hooks";
import { setUser } from "@/lib/store/slices/authSlice";

import Landing from "./Landing";

export default function LandingEntry() {
  const router = useRouter();
  const dispatch = useAppDispatch();

  const [legacyChecked, setLegacyChecked] = useState(false);

  const {
    data: user,
    isLoading,

  } = apiSlice.endpoints.getMe.useQuery();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);

    const reset = params.get("reset_password");
    const slate = params.get("slate");
    const experience = params.get("experience");

    if (reset) {
      router.replace(`/reset-password?token=${encodeURIComponent(reset)}`);
      return;
    }

    if (experience) {
      router.replace(`/experiences/${encodeURIComponent(experience)}`);
      return;
    }

    if (slate) {
      router.replace(`/individual/results?slate=${encodeURIComponent(slate)}`);
      return;
    }

    if (params.has("verify_email")) {
      router.replace("/login");
      return;
    }

    setLegacyChecked(true);
  }, [router]);

  useEffect(() => {
    if (user && legacyChecked) {
      dispatch(setUser(user));
      router.replace("/discover");
    }
  }, [user, legacyChecked, dispatch, router]);

  if (!legacyChecked || isLoading || user) {
    return (
      <main className="route-loading" role="status">
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
          <Link href="/login">ورود</Link>

          <Link href="/signup" className="landing-signup">
            ثبت‌نام
          </Link>
        </nav>
      </header>

      <main id="main" className="page-shell">
        <Landing start={() => router.push("/login?next=%2Findividual")} />
      </main>

      <footer className="site-footer landing-footer">
        <span>مودیگو · با ریتم تو</span>
        <span>یه کم وقت برای خودت، بدون باید.</span>
      </footer>
    </div>
  );
}
