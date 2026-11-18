"use client";

import Image from "next/image";
import Link from "next/link";

import { paths } from "@/lib/navigation";
import { useAppSelector } from "@/lib/store/hooks";
import { apiSlice } from "@/lib/store/api/apiSlice";

import Icon from "@/components/Icon";
import Pwa from "@/components/Pwa";

export default function AppHeader() {
  const user = useAppSelector((state) => state.auth.user);

  const { data: activeData } = apiSlice.endpoints.getActiveExperience.useQuery(
    undefined,
    {
      skip: !user,
    },
  );

  const activeExperience = activeData?.experience;

  return (
    <header className="site-header">
      <Link
        href={user ? paths.dashboard : paths.landing}
        className="wordmark"
        aria-label="مودیگو، صفحهٔ اصلی"
      >
        <Image
          src="/brand/moodigo-wordmark.png"
          alt="مودیگو"
          width={150}
          height={36}
          priority
          className="brand-wordmark"
        />
      </Link>

      <div className="header-caption">یه کم وقت برای خودت.</div>

      <div className="header-actions">
        <Pwa />

        {user && activeExperience?.status === "active" && (
          <Link
            className="active-link"
            href={`/experiences/${encodeURIComponent(activeExperience.id)}`}
          >
            <span className="status-dot" />
            تجربهٔ بازت
          </Link>
        )}

        {user ? (
          <>
            <Link
              href={paths.dashboard}
              className="account-button"
              aria-label="پنل کاربری"
            >
              <Icon name="user" size={19} />

              <span>{user.display_name || "حساب من"}</span>
            </Link>

            {user.role !== "user" && (
              <Link href={paths.admin} className="text-button">
                کارگاه محتوا
              </Link>
            )}
          </>
        ) : (
          <Link href={paths.login} className="header-login">
            <Icon name="user" size={17} />
            ورود
            <span className="login-extra">/ ساخت حساب</span>
          </Link>
        )}
      </div>
    </header>
  );
}
