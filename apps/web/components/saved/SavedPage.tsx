"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { paths } from "@/lib/navigation";
import { apiSlice, useGetSavedQuery } from "@/lib/store/api/apiSlice";
import { toApiError } from "@/lib/store/api/baseQuery";

import { isUnauthorized, usePrivatePageAuth } from "@/lib/usePrivatePageAuth";

import { Button, Empty } from "@/components/ui";

export default function SavedPage() {
  const router = useRouter();

  const { user, redirecting, authError, retryAuth, expireSession } =
    usePrivatePageAuth(paths.saved);

  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");

  const savedQuery = useGetSavedQuery(undefined, {
    skip: !user || redirecting,
  });

  const [removeSaved, { isLoading: isRemoving }] =
    apiSlice.endpoints.removeSaved.useMutation();

  useEffect(() => {
    if (isUnauthorized(savedQuery.error)) {
      expireSession();
    }
  }, [savedQuery.error, expireSession]);

  const handleRemove = async (activityId: string) => {
    if (isRemoving) return;

    setNotice("");
    setActionError("");

    try {
      await removeSaved(activityId).unwrap();

      setNotice("از ذخیره‌ها برداشته شد.");
    } catch (error) {
      const apiError = toApiError(error);

      if (apiError.status === 401) {
        expireSession();
        return;
      }

      setActionError(apiError.message);
    }
  };

  if (!user || redirecting) {
    return (
      <main id="main" className="page-shell">
        {authError ? (
          <div className="error-banner" role="alert">
            <p>بررسی حساب انجام نشد.</p>

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

  const saved = savedQuery.data?.items ?? [];

  return (
    <main
      id="main"
      className="page-shell"
      aria-busy={savedQuery.isLoading || isRemoving}
    >
      <section>
        <span className="eyebrow">برای یه وقت دیگه</span>

        <h1>چیزهایی که نگه داشتی.</h1>

        <p className="intro">لازم نیست نوبتشون همین امروز باشه.</p>

        {actionError && (
          <div className="error-banner" role="alert">
            <p>{actionError}</p>

            <button
              type="button"
              className="text-button"
              onClick={() => setActionError("")}
            >
              بستن
            </button>
          </div>
        )}

        <div className="status-region" role="status" aria-live="polite">
          {notice && <p className="notice-message">{notice}</p>}
        </div>

        {savedQuery.isLoading || savedQuery.isUninitialized ? (
          <div className="loading-state" role="status">
            <p>در حال دریافت ذخیره‌ها…</p>
          </div>
        ) : savedQuery.isError ? (
          <div className="empty-state" role="alert">
            <h2>دریافت ذخیره‌ها انجام نشد.</h2>

            <Button secondary onClick={() => void savedQuery.refetch()}>
              تلاش دوباره
            </Button>
          </div>
        ) : saved.length === 0 ? (
          <Empty title="اینجا هنوز خلوت و آرومه.">
            <p>هر پیشنهادی دوست داشتی، برای بعد نگهش دار.</p>

            <Button onClick={() => router.push(paths.questions)}>
              یه پیشنهاد ببینم
            </Button>
          </Empty>
        ) : (
          <div className="saved-list">
            {saved.map((item) => (
              <article key={item.activity_id} className="saved-card">
                <div>
                  <h2>
                    {item.unavailable
                      ? "فعلاً در دسترس نیست"
                      : (item.content?.title ?? "فعالیت بدون عنوان")}
                  </h2>

                  <p className="muted">{item.content?.teaser}</p>
                </div>

                <div className="inline-actions">
                  <Button
                    secondary
                    disabled={
                      isRemoving || item.unavailable || !item.revision_id
                    }
                    onClick={() => {
                      if (!item.revision_id) return;

                      router.push(
                        `/activities/${encodeURIComponent(item.revision_id)}?from=saved`,
                      );
                    }}
                  >
                    ببینمش
                  </Button>

                  <button
                    type="button"
                    className="text-button"
                    disabled={isRemoving}
                    onClick={() => void handleRemove(item.activity_id)}
                  >
                    {isRemoving ? "یه لحظه…" : "بردار"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
