"use client";

import { useEffect, useRef, useState } from "react";

import { skipToken } from "@reduxjs/toolkit/query";
import { useRouter, useSearchParams } from "next/navigation";

import type { Slot } from "@/types";

import { number } from "@/lib/api";
import { paths } from "@/lib/navigation";
import { useAuth } from "@/lib/hooks/useAuth";

import { useAppSelector } from "@/lib/store/hooks";
import { apiSlice, useGetSavedQuery } from "@/lib/store/api/apiSlice";

import { toApiError } from "@/lib/store/api/baseQuery";

import SingleSuggestion from "@/components/SingleSuggestion";
import { Button } from "@/components/ui";

export default function IndividualResultsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const { user, expireSession } = useAuth();

  const sessionId = searchParams.get("slate");

  const context = useAppSelector((state) => state.individual.context);

  const sessionQuery = apiSlice.endpoints.getSession.useQuery(
    sessionId ?? skipToken,
    {
      refetchOnMountOrArgChange: true,
    },
  );

  const savedQuery = useGetSavedQuery(undefined, {
    skip: !user,
  });

  const [replaceSuggestion] =
    apiSlice.endpoints.replaceSuggestion.useMutation();

  const [navigateSession] = apiSlice.endpoints.navigateSession.useMutation();

  const [saveActivity] = apiSlice.endpoints.saveActivity.useMutation();

  const [removeSaved] = apiSlice.endpoints.removeSaved.useMutation();

  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const lock = useRef(false);

  const returnTo = sessionId
    ? `${paths.results}?slate=${encodeURIComponent(sessionId)}`
    : paths.questions;

  // Use currentData to avoid showing another session's
  // cached result while the URL is changing.
  const slate = sessionQuery.currentData;

  const busy = working || sessionQuery.isFetching || savedQuery.isFetching;

  useEffect(() => {
    if (!sessionId) {
      router.replace(paths.questions);
    }
  }, [sessionId, router]);

  useEffect(() => {
    const errors = [sessionQuery.error, savedQuery.error];

    if (
      errors.some(
        (value) =>
          typeof value === "object" &&
          value !== null &&
          "status" in value &&
          value.status === 401,
      )
    ) {
      expireSession(returnTo);
    }
  }, [sessionQuery.error, savedQuery.error, expireSession, returnTo]);

  const handleFailure = async (failure: unknown): Promise<void> => {
    const apiError = toApiError(failure);

    if (apiError.status === 401) {
      expireSession(returnTo);
      return;
    }

    // Refresh the version after a concurrency conflict.
    if (
      [
        "VERSION_CONFLICT",
        "REPLACEMENT_LIMIT",
        "HISTORY_NOT_AT_END",
        "HISTORY_BOUNDARY",
      ].includes(apiError.code)
    ) {
      try {
        await sessionQuery.refetch().unwrap();
      } catch {
        // Keep the original error message.
        // The query error state can be retried separately.
      }
    }

    setError(apiError.message);
  };

  const perform = async (action: () => Promise<void>): Promise<void> => {
    if (lock.current || busy) return;

    lock.current = true;
    setWorking(true);
    setError("");
    setNotice("");

    try {
      await action();
    } catch (failure) {
      await handleFailure(failure);
    } finally {
      lock.current = false;
      setWorking(false);
    }
  };

  const handleReplace = (item: Slot) => {
    if (!slate) return;

    void perform(async () => {
      const result = await replaceSuggestion({
        sessionId: slate.id,
        slotId: item.slot_id,
        expected_version: slate.version,
      }).unwrap();

      if (!result.replaced) {
        setNotice(
          "فعلاً گزینهٔ تازه‌ای با همین شرایط نداریم. سهمیهٔ تعویضت مصرف نشد.",
        );
      }

      // RTK Query automatically refetches the
      // invalidated Session query.
    });
  };

  const handleBrowse = (direction: "previous" | "next") => {
    if (!slate) return;

    void perform(async () => {
      await navigateSession({
        sessionId: slate.id,
        direction,
        expected_version: slate.version,
      }).unwrap();
    });
  };

  const handleSave = (item: Slot) => {
    if (!item.activity_id) {
      setError("شناسهٔ فعالیت موجود نیست.");
      return;
    }

    const savedItems = savedQuery.data?.items ?? [];

    const isSaved = savedItems.some(
      (savedItem) => savedItem.activity_id === item.activity_id,
    );

    void perform(async () => {
      if (!item.activity_id) return;

      if (isSaved) {
        await removeSaved(item.activity_id).unwrap();
      } else {
        await saveActivity(item.activity_id).unwrap();
      }

      setNotice(isSaved ? "از ذخیره‌ها برداشته شد." : "برای بعد نگهش داشتیم.");
    });
  };

  const handleOpen = (item: Slot) => {
    if (!slate || !item.revision_id) {
      setError("شناسهٔ نسخهٔ پیشنهاد موجود نیست.");
      return;
    }

    const params = new URLSearchParams({
      from: "individual",
      slate: slate.id,
      slot: item.slot_id,
    });

    router.push(
      `/activities/${encodeURIComponent(item.revision_id)}?${params.toString()}`,
    );
  };

  const changeConditions = () => {
    router.push(paths.questions);
  };

  if (!sessionId) {
    return (
      <main id="main" className="page-shell" role="status">
        در حال بازگشت به سؤال‌ها…
      </main>
    );
  }

  if (sessionQuery.isError || savedQuery.isError) {
    return (
      <main id="main" className="page-shell">
        <section>
          <h1>دریافت پیشنهاد انجام نشد.</h1>

          <p className="intro">اتصال یا وضعیت پیشنهاد را بررسی کن.</p>

          <div className="inline-actions wrap">
            <Button
              secondary
              onClick={() => {
                void sessionQuery.refetch();
                void savedQuery.refetch();
              }}
            >
              تلاش دوباره
            </Button>

            <Button onClick={changeConditions}>برگشت به سؤال‌ها</Button>
          </div>
        </section>
      </main>
    );
  }

  if (
    !slate ||
    sessionQuery.isLoading ||
    savedQuery.isLoading ||
    savedQuery.isUninitialized
  ) {
    return (
      <main id="main" className="page-shell">
        <div className="loading-state" role="status">
          <p>در حال دریافت پیشنهادت…</p>
        </div>
      </main>
    );
  }

  const summary = slate.context_summary ?? context;
  const item = slate.items[0];
  const remainingMinutes = item?.unavailable || item?.total_minutes == null
    ? 0 : summary.available_minutes - item.total_minutes;
  const alternative = slate.venue_alternative;
  const budgetAlternative = slate.budget_alternative;
  const savedItems = savedQuery.data?.items ?? [];

  return (
    <main id="main" className="page-shell" aria-busy={busy}>
      {error && (
        <div className="error-banner" role="alert">
          <p>{error}</p>

          <button
            type="button"
            className="text-button"
            onClick={() => setError("")}
          >
            بستن
          </button>
        </div>
      )}

      <div className="status-region" role="status" aria-live="polite">
        {notice && <p className="notice-message">{notice}</p>}
      </div>

      <section>
        <div className="section-heading">
          <div>
            <span className="eyebrow">برای همین حال و همین وقت</span>

            <h1>این یکی شاید الان بهت بچسبه.</h1>

            <p className="intro">
              اگه به دلت ننشست، تا شش بار یه پیشنهاد تازه ببین.
            </p>
          </div>

          <button
            type="button"
            className="text-button"
            disabled={busy}
            onClick={changeConditions}
          >
            شرایطم رو عوض کنم <span aria-hidden="true">↗</span>
          </button>
        </div>

        <div className="constraint-summary">
          <span>{number(summary.available_minutes)} دقیقه</span>

          <span>
            {summary.social_mode === "solo"
              ? "تنهایی"
              : summary.social_mode === "together"
                ? "با همراه"
                : "تنها یا با همراه"}
          </span>

          <span>
            {
              {
                home: "خونه",
                outdoor: "هوای آزاد",
                indoor_public: "سرپوشیده",
                away_from_home: "بیرون از خونه",
                any: "هر جا شد",
              }[summary.venue]
            }
          </span>

          {summary.allow_venue_planning && summary.city && <span>{summary.city}</span>}

          <span>
            {summary.budget.mode === "free"
              ? "رایگان"
              : summary.budget.mode === "cap"
                ? "تا " + number(summary.budget.cap_toman!) + " تومان"
                : "هزینهٔ منعطف"}
          </span>
        </div>

        <SingleSuggestion
          slate={slate}
          busy={busy}
          saved={savedItems.some(
            (item) => item.activity_id === slate.items[0]?.activity_id,
          )}
          open={handleOpen}
          save={handleSave}
          replace={handleReplace}
          browse={handleBrowse}
          changeConditions={changeConditions}
        />
        {remainingMinutes > 0 && (
          <p className="hint">
            بعد از این پیشنهاد، {number(remainingMinutes)} دقیقه از وقتت می‌مونه.
          </p>
        )}
        {summary.budget.mode === "cap" && item?.cost_range_toman?.max === 0 && !item.unavailable && (
          <p className="hint">این پیشنهاد رایگانه و از بودجه‌ات خرج نمی‌شه.</p>
        )}
        {alternative && (
          <div className="notice-message">
            <p>
              اگه محیط رو به «{{
                home: "خونه", outdoor: "هوای آزاد", indoor_public: "جای سرپوشیده",
              }[alternative.venue]}» تغییر بدی، گزینهٔ طولانی‌تری هست:
              {" "}{alternative.title} ({number(alternative.total_minutes)} دقیقه).
            </p>
            <Button secondary disabled={busy} onClick={changeConditions}>تغییر محیط در سؤال‌ها</Button>
          </div>
        )}
        {budgetAlternative && (
          <div className="notice-message">
            <p>
              یه گزینه با قیمت نامعلوم هم هست: {budgetAlternative.title}
              {" "}({number(budgetAlternative.total_minutes)} دقیقه).
              برای دیدنش می‌تونی بودجهٔ منعطف رو انتخاب کنی. قبل از رفتن قیمت رو از محل بپرس.
            </p>
            <Button secondary disabled={busy} onClick={changeConditions}>تغییر بودجه در سؤال‌ها</Button>
          </div>
        )}
      </section>
    </main>
  );
}
