"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { badgeNames, number } from "@/lib/api";
import { paths } from "@/lib/navigation";
import { apiSlice } from "@/lib/store/api/apiSlice";
import { isUnauthorized, usePrivatePageAuth } from "@/lib/usePrivatePageAuth";

import { Button, Empty } from "@/components/ui";

const dimensionNames: Record<string, string> = {
  detachment: "فاصله از روزمرگی",
  relaxation: "یه مکث آروم",
  autonomy: "به سلیقهٔ خودت",
  mastery: "یه چیز تازه",
  meaning: "یه لحظهٔ باارزش",
  affiliation: "کنار هم",
};

const statusNames: Record<string, string> = {
  active: "در جریان",
  completed: "تموم‌شده",
  cancelled: "لغوشده",
  expired: "بسته‌شده",
};

const dateFormatter = new Intl.DateTimeFormat("fa-IR", {
  dateStyle: "medium",
});

export default function JourneyPage() {
  const router = useRouter();

  const { user, redirecting, authError, retryAuth, expireSession } =
    usePrivatePageAuth(paths.journey);

  const skip = !user || redirecting;

  const journeyQuery = apiSlice.endpoints.getJourney.useQuery(undefined, {
    skip,
  });

  const historyQuery = apiSlice.endpoints.getExperienceHistory.useQuery(
    undefined,
    { skip },
  );

  const preferencesQuery = apiSlice.endpoints.getPreferences.useQuery(
    undefined,
    { skip },
  );

  useEffect(() => {
    const errors = [
      journeyQuery.error,
      historyQuery.error,
      preferencesQuery.error,
    ];

    if (errors.some(isUnauthorized)) {
      expireSession();
    }
  }, [
    journeyQuery.error,
    historyQuery.error,
    preferencesQuery.error,
    expireSession,
  ]);

  const retryQueries = () => {
    void journeyQuery.refetch();
    void historyQuery.refetch();
    void preferencesQuery.refetch();
  };

  if (!user || redirecting) {
    return (
      <main id="main" className="page-shell">
        {authError ? (
          <div className="error-banner" role="alert">
            <p>
              بررسی حساب انجام نشد. اتصال سرور را بررسی کن و دوباره تلاش کن.
            </p>

            <Button secondary onClick={retryAuth}>
              تلاش دوباره
            </Button>
          </div>
        ) : (
          <div className="loading-state" role="status">
            <p>در حال بررسی حساب…</p>
          </div>
        )}
      </main>
    );
  }

  const hasQueryError =
    journeyQuery.isError || historyQuery.isError || preferencesQuery.isError;

  const isLoading =
    journeyQuery.isLoading ||
    historyQuery.isLoading ||
    preferencesQuery.isLoading ||
    journeyQuery.isUninitialized ||
    historyQuery.isUninitialized ||
    preferencesQuery.isUninitialized;

  if (hasQueryError) {
    return (
      <main id="main" className="page-shell">
        <section>
          <span className="eyebrow">با ریتم خودت</span>
          <h1>مسیر کوچیک تو.</h1>

          <div className="error-banner" role="alert">
            <p>دریافت اطلاعات مسیر انجام نشد. لطفاً دوباره تلاش کن.</p>

            <Button secondary onClick={retryQueries}>
              تلاش دوباره
            </Button>
          </div>
        </section>
      </main>
    );
  }

  if (
    isLoading ||
    !journeyQuery.data ||
    !historyQuery.data ||
    !preferencesQuery.data
  ) {
    return (
      <main id="main" className="page-shell">
        <div className="loading-state" role="status">
          <p>در حال دریافت مسیرت…</p>
        </div>
      </main>
    );
  }

  const journey = journeyQuery.data;
  const history = historyQuery.data.items;
  const preferences = preferencesQuery.data;

  const showGamification = preferences.preferences.show_gamification !== false;

  return (
    <main id="main" className="page-shell">
      <section>
        <span className="eyebrow">با ریتم خودت</span>

        <h1>مسیر کوچیک تو.</h1>

        <p className="intro">
          اینجا خبری از عقب‌افتادن نیست. فقط لحظه‌هایی که برای خودت ساختی.
        </p>

        {showGamification && (
          <>
            <div className="journey-stats">
              <div>
                <strong>{number(journey.total_points)}</strong>

                <span>امتیاز اکتشاف</span>
              </div>

              <div>
                <strong>{number(journey.rewarded_completions)}</strong>

                <span>تجربهٔ امتیازدار</span>
              </div>
            </div>

            {journey.badges.length > 0 && (
              <div className="badge-list">
                {journey.badges.map((key) => (
                  <span key={key} className="earned-badge">
                    ✧ {badgeNames[key] ?? key}
                  </span>
                ))}
              </div>
            )}

            {journey.completed_dimensions.length > 0 && (
              <div className="dimension-list">
                {journey.completed_dimensions.map((key) => (
                  <span key={key}>{dimensionNames[key] ?? key}</span>
                ))}
              </div>
            )}
          </>
        )}

        <h2 className="history-title">لحظه‌های قبلی</h2>

        {history.length > 0 ? (
          <div className="history-list">
            {history.map((experience) => (
              <article key={experience.id}>
                <span aria-hidden="true">
                  {experience.status === "completed" ? "✧" : "◌"}
                </span>

                <div>
                  <h3>
                    {experience.unavailable
                      ? "تجربهٔ کنارگذاشته‌شده"
                      : (experience.content_snapshot?.title ??
                        "تجربهٔ بدون عنوان")}
                  </h3>

                  <p className="hint">
                    <time dateTime={experience.started_at}>
                      {dateFormatter.format(new Date(experience.started_at))}
                    </time>

                    {" · "}

                    {statusNames[experience.status] ?? experience.status}
                  </p>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <Empty title="اولین لحظه هنوز در راهه.">
            <p>هر وقت دلت خواست، یه تجربهٔ کوچیک انتخاب کن.</p>

            <Button onClick={() => router.push(paths.questions)}>
              بریم انتخاب کنیم
            </Button>
          </Empty>
        )}
      </section>
    </main>
  );
}
