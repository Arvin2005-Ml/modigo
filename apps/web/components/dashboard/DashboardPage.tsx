"use client";

import { useEffect, type ReactNode } from "react";
import Link from "next/link";

import Icon, { type IconName } from "@/components/Icon";
import MomentArt from "@/components/MomentArt";
import { paths } from "@/lib/navigation";
import { apiSlice } from "@/lib/store/api/apiSlice";
import { isUnauthorized, usePrivatePageAuth } from "@/lib/usePrivatePageAuth";
import type { Experience } from "@/types";

import styles from "./DashboardPage.module.css";

const navigation = [
  { href: paths.dashboard, icon: "dashboard", label: "نمای کلی" },
  { href: paths.questions, icon: "spark", label: "پیشنهاد برای من" },
  { href: paths.discover, icon: "leaf", label: "کشف فعالیت‌ها" },
  { href: paths.saved, icon: "bookmark", label: "ذخیره‌ها" },
  { href: paths.journey, icon: "journey", label: "مسیر من" },
  { href: paths.settings, icon: "settings", label: "تنظیمات" },
] as const satisfies readonly { href: string; icon: IconName; label: string }[];

const statusNames: Record<Experience["status"], string> = {
  active: "در جریان",
  completed: "انجام‌شده",
  cancelled: "لغوشده",
  expired: "بسته‌شده",
};

function LoadError({ children, retry }: { children: ReactNode; retry: () => void }) {
  return (
    <div className={styles.loadError} role="alert">
      <p>{children}</p>
      <button type="button" className="text-button" onClick={retry}>
        تلاش دوباره
      </button>
    </div>
  );
}

export default function DashboardPage() {
  const { user, authError, retryAuth, expireSession } =
    usePrivatePageAuth(paths.dashboard);
  const skip = !user;
  const activeQuery = apiSlice.endpoints.getActiveExperience.useQuery(undefined, { skip });
  const historyQuery = apiSlice.endpoints.getExperienceHistory.useQuery(undefined, { skip });
  const savedQuery = apiSlice.endpoints.getSaved.useQuery(undefined, { skip });

  const sessionExpired = [activeQuery.error, historyQuery.error, savedQuery.error]
    .some(isUnauthorized);

  useEffect(() => {
    if (sessionExpired) expireSession();
  }, [sessionExpired, expireSession]);

  if (!user || sessionExpired) {
    return (
      <main id="main" className="page-shell">
        {authError ? (
          <LoadError retry={retryAuth}>بررسی حساب انجام نشد.</LoadError>
        ) : (
          <p className="loading-state" role="status">در حال بررسی حساب…</p>
        )}
      </main>
    );
  }

  const active = activeQuery.isSuccess ? activeQuery.data.experience : null;
  const recent = historyQuery.data?.items
    .filter((experience) => experience.status !== "active")
    .slice(0, 3);
  const saved = savedQuery.data?.items.slice(0, 3);
  const dateFormatter = new Intl.DateTimeFormat("fa-IR", {
    dateStyle: "medium",
    timeZone: user.timezone,
  });

  return (
    <main id="main" className={`page-shell ${styles.dashboard}`}>
      <div className={styles.heading}>
        <h1>پنل کاربری</h1>
        <p>{user.display_name ? <>سلام، <bdi>{user.display_name}</bdi>!</> : "سلام، خوش اومدی!"}</p>
      </div>

      <section className={styles.hero} aria-labelledby="dashboard-next">
        <div>
          <h2 id="dashboard-next">{active ? "فعالیت در جریان" : "برای وقت آزادت چی می‌چسبه؟"}</h2>
          <p>
            {active
              ? (active.unavailable ? "این فعالیت از دسترس خارج شده." : active.content_snapshot?.title ?? "فعالیتی که شروع کردی")
              : "چند سؤال کوتاه جواب بده تا یه پیشنهاد متناسب با همین الان بگیری."}
          </p>
          <Link
            className="button-primary"
            href={active ? `/experiences/${encodeURIComponent(active.id)}` : paths.questions}
          >
            {active ? (active.unavailable ? "وضعیت فعالیت" : "ادامهٔ فعالیت") : "گرفتن پیشنهاد"}
            <Icon name="arrow" size={18} />
          </Link>
          {activeQuery.isError && (
            <LoadError retry={activeQuery.refetch}>وضعیت فعالیت در جریان دریافت نشد.</LoadError>
          )}
        </div>
        <div className={styles.art} aria-hidden="true">
          <MomentArt variant={1} />
        </div>
      </section>

      <nav className={styles.sidebar} aria-label="پنل کاربری">
        {navigation.map(({ href, icon, label }) => (
          <Link key={href} href={href} aria-current={href === paths.dashboard ? "page" : undefined}>
            <Icon name={icon} size={20} />
            {label}
          </Link>
        ))}
      </nav>

      <div className={styles.panels}>
        <section className={styles.panel} aria-labelledby="dashboard-recent">
          <div className={styles.panelHeader}>
            <h2 id="dashboard-recent"><Icon name="clock" size={19} /> فعالیت‌های اخیر</h2>
            <Link href={paths.journey} className="text-button">دیدن مسیر من</Link>
          </div>
          {historyQuery.isError ? (
            <LoadError retry={historyQuery.refetch}>سابقهٔ فعالیت‌ها دریافت نشد.</LoadError>
          ) : !recent ? (
            <p role="status">در حال دریافت سابقه…</p>
          ) : recent.length ? (
            <ul className={styles.items}>
              {recent.map((experience) => (
                <li key={experience.id}>
                  <strong>{experience.unavailable ? "فعالیت کنارگذاشته‌شده" : experience.content_snapshot?.title ?? "فعالیت بدون عنوان"}</strong>
                  <p>
                    {statusNames[experience.status]} ·{" "}
                    <time dateTime={experience.started_at}>{dateFormatter.format(new Date(experience.started_at))}</time>
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p>هنوز فعالیتی در سابقه‌ات ثبت نشده.</p>
          )}
        </section>

        <section className={styles.panel} aria-labelledby="dashboard-saved">
          <div className={styles.panelHeader}>
            <h2 id="dashboard-saved"><Icon name="bookmark" size={19} /> ذخیره‌ها</h2>
            <Link href={paths.saved} className="text-button">دیدن همه</Link>
          </div>
          {savedQuery.isError ? (
            <LoadError retry={savedQuery.refetch}>ذخیره‌ها دریافت نشدند.</LoadError>
          ) : !saved ? (
            <p role="status">در حال دریافت ذخیره‌ها…</p>
          ) : saved.length ? (
            <ul className={styles.items}>
              {saved.map((item) => (
                <li key={item.activity_id}>
                  {!item.unavailable && item.content?.title && item.revision_id ? (
                    <Link
                      className={styles.savedLink}
                      href={`/activities/${encodeURIComponent(item.revision_id)}?from=saved`}
                    >
                      <strong>{item.content.title}</strong>
                      <Icon name="arrow" size={16} />
                    </Link>
                  ) : (
                    <p>این فعالیت فعلاً در دسترس نیست.</p>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p>فعالیت‌هایی که برای بعد ذخیره می‌کنی، اینجا می‌مونن.</p>
          )}
        </section>
      </div>
    </main>
  );
}
