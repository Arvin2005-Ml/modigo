"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  isAuthPath,
  paths,
  viewFromPathname,
  type AppView,
} from "@/lib/navigation";

import { useAuth } from "@/lib/hooks/useAuth";
import { ApiError, badgeNames, number, refreshCsrf } from "@/lib/api";
import { useAppDispatch, useAppSelector } from "@/lib/store/hooks";
import { apiSlice, useGetPreferencesQuery } from "@/lib/store/api/apiSlice";
import { createApiClient } from "@/lib/store/api/apiClient";
import { toApiError } from "@/lib/store/api/baseQuery";
import { setUser, clearUser } from "@/lib/store/slices/authSlice";
import type { Slate, Slot, Revision, Experience, Award } from "@/types";

import Auth from "./Auth";
import Admin from "./Admin";
import { ContentDetails } from "./Activity";
import { Button, Empty, Note } from "./ui";
import Icon from "./Icon";

export default function Funilo() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const view = viewFromPathname(pathname);
  const { user, status, expireSession } = useAuth();

  const resetToken =
    pathname === paths.reset ? searchParams.get("token") : null;

  const dispatch = useAppDispatch();
  const client = useMemo(() => createApiClient(dispatch), [dispatch]);

  const preferencesQuery = useGetPreferencesQuery(undefined, { skip: !user });

  const activeExperienceQuery = apiSlice.endpoints.getActiveExperience.useQuery(
    undefined,
    {
      skip: !user,
    },
  );

  const preferences = preferencesQuery.data ?? null;

  const [slate, setSlate] = useState<Slate | null>(null);
  const [detail, setDetail] = useState<Revision | null>(null);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [experience, setExperience] = useState<Experience | null>(null);
  const [award, setAward] = useState<Award | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [feedbackDone, setFeedbackDone] = useState(false);

  const [routeLoading, setRouteLoading] = useState(false);

  const main = useRef<HTMLElement>(null);
  const lock = useRef(false);

  // Invalidate the old check-in whenever the
  // server-side preferences version changes.

  const navigate = useCallback(
    (next: AppView) => {
      setError("");
      setNotice("");

      const staticPaths: Partial<Record<AppView, string>> = {
        discover: paths.discover,
        auth: paths.login,
        questions: paths.questions,
        saved: paths.saved,
        journey: paths.journey,
        settings: paths.settings,
        admin: paths.admin,
      };

      const href = staticPaths[next];

      if (href) {
        router.push(href);
      }
    },
    [router],
  );

  const clearPrivateState = useCallback(() => {
    setSlate(null);
    setDetail(null);
    setSlot(null);
    setExperience(null);
    setAward(null);
  }, []);

  const report = useCallback(
    (error: unknown) => {
      setError(
        error instanceof Error
          ? error.message
          : "یه مشکلی پیش اومد؛ دوباره امتحان کن.",
      );

      if (error instanceof ApiError && error.status === 401) {
        clearPrivateState();

        const query = searchParams.toString();

        const returnTo = pathname + (query ? `?${query}` : "");

        expireSession(returnTo);
      }
    },
    [clearPrivateState, expireSession, pathname, searchParams],
  );

  const run = useCallback(
    async (work: () => Promise<void>) => {
      if (lock.current) return;
      lock.current = true;
      setBusy(true);
      setError("");
      setNotice("");
      try {
        await work();
      } catch (e) {
        report(e);
      } finally {
        lock.current = false;
        setBusy(false);
      }
    },
    [report],
  );

  useEffect(() => {
    const queryError = preferencesQuery.error;

    if (queryError && "status" in queryError && queryError.status === 401) {
      report(toApiError(queryError));
    }
  }, [preferencesQuery.error, report]);

  useEffect(() => {
    if (status !== "authenticated" || !user) {
      setRouteLoading(false);
      return;
    }

    let cancelled = false;

    const loadRoute = async () => {
      const needsLoading = ["detail", "active", "complete"].includes(view);

      if (!needsLoading) {
        setRouteLoading(false);
        return;
      }

      setRouteLoading(true);

      try {
        if (view === "detail") {
          const revisionId = pathname.split("/")[2];

          const revision = await client.getRevision(revisionId);

          if (cancelled) return;

          setDetail(revision);

          if (searchParams.get("from") === "individual") {
            const slateId = searchParams.get("slate");

            const slotId = searchParams.get("slot");

            if (slateId && slotId) {
              const session = await client.getSession(slateId);

              if (cancelled) return;

              setSlate(session);

              setSlot(
                session.items.find(
                  (item) =>
                    item.slot_id === slotId && item.revision_id === revisionId,
                ) ?? null,
              );
            } else {
              setSlot(null);
            }
          } else {
            setSlot(null);
          }
        }

        if (view === "active") {
          const active = await client.getActiveExperience();

          if (!cancelled) {
            setExperience(active.experience);
          }
        }

        if (view === "complete" && !award) {
          // The current Backend does not expose
          // a dedicated award recovery endpoint.
          router.replace(paths.journey);
        }
      } catch (error) {
        if (!cancelled) {
          report(error);
        }
      } finally {
        if (!cancelled) {
          setRouteLoading(false);
        }
      }
    };

    void loadRoute();

    return () => {
      cancelled = true;
    };
  }, [
    status,
    user,
    pathname,
    searchParams,
    view,
    client,
    router,
    report,
    award,
  ]);

  useEffect(() => {
    const heading = main.current?.querySelector("h1");

    if (heading) {
      heading.setAttribute("tabindex", "-1");
      heading.focus({ preventScroll: true });
    }

    window.scrollTo({
      top: 0,
      behavior: "instant",
    });
  }, [view, routeLoading]);

  const start = () =>
    run(async () => {
      if (!slate || !slot || searchParams.get("from") !== "individual") {
        throw new Error(
          "این فعالیت ابتدا باید از یک پیشنهاد معتبر انتخاب شود.",
        );
      }

      const result = await client.startExperience({
        recommendation_session_id: slate.id,
        slot_id: slot.slot_id,
        revision_id: slot.revision_id,
      });

      setExperience(result);

      router.push(`/experiences/${encodeURIComponent(result.id)}`);
    });

  const complete = () =>
    run(async () => {
      if (!experience) {
        throw new Error("تجربهٔ فعال پیدا نشد.");
      }

      const result = await client.completeExperience(experience.id);

      setExperience(result.experience);
      setAward(result.award);
      setFeedbackDone(false);

      router.push(
        `/experiences/${encodeURIComponent(result.experience.id)}/complete`,
      );
    });

  const showJourney = () => {
    navigate("journey");
  };

  const route = (next: AppView) => {
    if (!user) {
      const targets: Partial<Record<AppView, string>> = {
        discover: paths.discover,
        questions: paths.questions,
        saved: paths.saved,
        journey: paths.journey,
        settings: paths.settings,
        admin: paths.admin,
      };

      const target = targets[next] ?? paths.discover;

      router.push(`${paths.login}?next=${encodeURIComponent(target)}`);
      return;
    }

    navigate(next);
  };

  const returnHome = () => {
    route("questions");
  };

  // These routes now render their own page content.

  if (
    isAuthPath(pathname) ||
    view === "auth" ||
    view === "saved" ||
    view === "journey" ||
    view === "settings" ||
    view === "questions" ||
    view === "discover" ||
    view === "results"
  ) {
    return null;
  }

  const activeExperience =
    activeExperienceQuery.data?.experience ??
    (experience?.status === "active" ? experience : null);

  return (
    <main
      id="main"
      ref={main}
      className={`page-shell ${view === "admin" ? "wide" : ""}`}
      aria-busy={busy}
    >
      {error && (
        <div className="error-banner" role="alert">
          <p>{error}</p>
          <button
            className="text-button"
            onClick={() => setError("")}
            aria-label="بستن پیام خطا"
          >
            بستن
          </button>
        </div>
      )}
      <div className="status-region" role="status" aria-live="polite">
        {notice && <p className="notice-message">{notice}</p>}
      </div>

      {routeLoading ? (
        <div className="loading-state" role="status">
          <span className="loading-flower" aria-hidden="true">
            <Icon name="spark" size={42} />
          </span>
          <p>یه لحظه، داریم آماده می‌شیم…</p>
        </div>
      ) : (
        <>
          {view === "detail" && detail && (
            <section className="detail-column">
              <button
                className="text-button back-button"
                onClick={() => {
                  const from = searchParams.get("from");
                  const slateId = searchParams.get("slate");

                  if (from === "individual" && slateId) {
                    router.push(
                      `/individual/results?slate=${encodeURIComponent(slateId)}`,
                    );
                  } else if (from === "saved") {
                    router.push(paths.saved);
                  } else {
                    const filters =
                      from === "discover" ? searchParams.get("filters") : null;
                    router.push(
                      filters ? `${paths.discover}?${filters}` : paths.discover,
                    );
                  }
                }}
              >
                <span aria-hidden="true">→</span> برگشت به انتخاب‌ها
              </button>
              <ContentDetails content={detail.content} />

              {searchParams.get("from") === "individual" &&
              slate &&
              slot &&
              slot.revision_id === pathname.split("/")[2] ? (
                <Button className="w-full" disabled={busy} onClick={start}>
                  {busy ? "یه لحظه…" : "همین رو شروع می‌کنم"}
                </Button>
              ) : (
                <>
                  <Note>
                    فعلاً شروع فعالیت تنها از مسیر Individual پشتیبانی می‌شه.
                    شروع مستقیم از خانه و ذخیره‌ها به تغییر قرارداد Backend نیاز
                    داره.
                  </Note>
                  <Button onClick={returnHome}>برای الان پیشنهاد بگیرم</Button>
                </>
              )}
            </section>
          )}

          {view === "active" &&
            (!experience ||
              experience.id !== pathname.split("/")[2] ||
              experience.status !== "active") && (
              <Empty title="تجربهٔ فعالی در این مسیر پیدا نشد.">
                <Button onClick={() => navigate("discover")}>
                  برگشت به خانه
                </Button>
              </Empty>
            )}

          {view === "active" &&
            experience &&
            experience.id === pathname.split("/")[2] &&
            experience.status === "active" && (
              <section className="detail-column">
                <span className="experience-label">
                  <span aria-hidden="true">●</span> وقتِ خودته
                </span>
                {experience.unavailable || !experience.content_snapshot ? (
                  <Empty title="دستور این تجربه دیگه در دسترس نیست.">
                    <p>می‌تونی تجربهٔ بازت رو تموم یا لغو کنی.</p>
                  </Empty>
                ) : (
                  <ContentDetails content={experience.content_snapshot} />
                )}
                <p className="hint">
                  زمان‌سنج و عجله‌ای در کار نیست.هر وقت برات کافی بود،همین‌جا
                  تمومش کن.
                </p>
                <div className="experience-actions">
                  <Button onClick={complete} disabled={busy}>
                    {busy ? "یه لحظه…" : "تمومش کردم"}
                  </Button>
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() =>
                      run(async () => {
                        await client.cancelExperience(experience.id);
                        setExperience(null);
                        returnHome();
                      })
                    }
                  >
                    این بار بی‌خیالش شدم
                  </button>
                </div>
              </section>
            )}
          {view === "complete" && experience && award && (
            <section className="completion-column">
              <div className="completion-symbol" aria-hidden="true">
                ✳
              </div>
              <span className="eyebrow">یه وقت کوچیک برای خودت ساختی</span>
              <h1>همین هم یه لحظهٔ خوب بود.</h1>
              <p className="intro">هرقدرش که انجام دادی،کافیه.</p>
              {preferences?.preferences.show_gamification !== false && (
                <div className="award-card">
                  <strong>
                    {award.points
                      ? "+" + number(award.points) + " امتیاز"
                      : "تجربه‌ات ثبت شد"}
                  </strong>
                  <p>
                    {award.points
                      ? "یه قدم به مسیر تجربه‌هات اضافه شد."
                      : award.reason === "RECENT_ACTIVITY"
                        ? "این تجربه رو همین هفته امتحان کردی؛امتیاز تازه‌ای اضافه نشد."
                        : "سهم امتیاز این بازه پر شده؛این لحظه توی مسیرت می‌مونه."}
                  </p>
                  {award.new_badges.map((key) => (
                    <span className="earned-badge" key={key}>
                      ✧ {badgeNames[key]}
                    </span>
                  ))}
                </div>
              )}
              {!feedbackDone ? (
                <div className="feedback">
                  <h2>چقدر بهت چسبید؟</h2>
                  <p className="hint">
                    اگه دوست داشتی بگو تا دفعهٔ بعد بهتر انتخاب کنیم.
                  </p>
                  <div className="feedback-choices">
                    {(
                      [
                        ["liked", "چسبید"],
                        ["neutral", "معمولی بود"],
                        ["disliked", "برای من نبود"],
                      ] as const
                    ).map(([rating, label]) => (
                      <Button
                        secondary
                        disabled={busy}
                        key={rating}
                        onClick={() =>
                          run(async () => {
                            await client.sendFeedback({
                              experienceId: experience.id,
                              rating,
                              reason: null,
                            });
                            setFeedbackDone(true);
                            setNotice("بازخوردت ثبت شد.");
                          })
                        }
                      >
                        {label}
                      </Button>
                    ))}
                  </div>
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() => setFeedbackDone(true)}
                  >
                    الان نمی‌خوام بگم
                  </button>
                </div>
              ) : (
                <p className="soft-note">
                  هر وقت خواستی،یه تجربهٔ تازه منتظرته.
                </p>
              )}
              <div className="inline-actions wrap">
                <Button onClick={returnHome}>یه پیشنهاد دیگه</Button>
                <Button secondary onClick={showJourney}>
                  مسیرم رو ببینم
                </Button>
              </div>
            </section>
          )}

          {view === "admin" && user && <Admin user={user} report={report} />}
        </>
      )}
    </main>
  );
}
