"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { number } from "@/lib/api";
import { guestActivities } from "@/lib/guest/catalog";
import { useStoredGuestSuggestion } from "@/lib/guest/suggestionStorage";
import { guestSignupPath, paths } from "@/lib/navigation";
import { itemOptions } from "@/lib/personalization";

const venueLabels = { home: "توی خونه", outdoor: "فضای باز", indoor_public: "جای سرپوشیده" };

export default function GuestResultPage() {
  const router = useRouter();
  const stored = useStoredGuestSuggestion();
  const activity = typeof stored === "string" ? guestActivities.find((item) => item.key === stored) : undefined;
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (stored === null) router.replace(paths.guestQuestions);
  }, [router, stored]);

  useEffect(() => {
    if (activity) heading.current?.focus({ preventScroll: true });
  }, [activity]);

  if (stored === undefined || stored === null) {
    return <main id="main" className="route-loading" role="status">در حال آماده‌سازی…</main>;
  }

  if (!activity) {
    return (
      <main id="main" className="route-loading">
        <h1>این پیشنهاد در دسترس نیست.</h1>
        <Link href={guestSignupPath} className="button-primary">برای پیشنهاد تازه ثبت‌نام کن</Link>
      </main>
    );
  }

  const items = itemOptions.filter(([item]) => activity.items?.includes(item)).map(([, label]) => label);
  const [min, max] = activity.people;
  const people = max === 1 ? "تک‌نفره" : `${number(min)}${min === max ? "" : ` تا ${number(max)}`} نفر`;

  return (
    <main id="main" className="page-shell">
      <article className="detail-column" aria-labelledby="guest-activity-title">
        <p className="eyebrow">پیشنهاد برای همین الان</p>
        <h1 id="guest-activity-title" ref={heading} tabIndex={-1}>{activity.title}</h1>
        <div className="detail-meta" role="group" aria-label="شرایط فعالیت">
          <span>حدود {number(activity.minutes)} دقیقه</span>
          <span>{venueLabels[activity.venue]}</span>
          <span>{people}</span>
          <span>{activity.city ? "هزینهٔ نامشخص" : "رایگان"}</span>
        </div>
        <div className="first-step">
          <h2 className="eyebrow">از اینجا شروع کن</h2>
          <p>{activity.instructions}</p>
        </div>
        {items.length > 0 && <p className="intro">وسایل لازم {items.join("، ")}</p>}
        {activity.city ? (
          <p className="intro">این مدت برای خود فعالیت در نظر گرفته شده. اگه نزدیکی، قبل از حرکت باز بودن، هزینه و زمان مسیر رو بررسی کن.</p>
        ) : activity.venue !== "home" && (
          <p className="intro">توی یه جای امن و مجاز که همین حالا در دسترسته انجامش بده.</p>
        )}
        <Link href={guestSignupPath} className="button-primary">ثبت‌نام برای پیشنهاد بعدی</Link>
      </article>
    </main>
  );
}
