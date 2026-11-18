"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import Image from "next/image";
import Link from "next/link";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  authModeFromPathname,
  isAuthPath,
  paths,
  safeNextPath,
  viewFromPathname,
  type AppView,
} from "@/lib/navigation";

import { ApiError, badgeNames, number, refreshCsrf } from "@/lib/api";
import { useAppDispatch, useAppSelector } from "@/lib/store/hooks";
import {
  apiSlice,
  useGetSavedQuery,
  useGetPreferencesQuery,
} from "@/lib/store/api/apiSlice";
import { createApiClient } from "@/lib/store/api/apiClient";
import { toApiError } from "@/lib/store/api/baseQuery";
import { setUser, clearUser } from "@/lib/store/slices/authSlice";
import type {
  Context,
  Slate,
  Slot,
  Revision,
  Experience,
  Award,
  Journey,
  ReplacementState,
} from "@/types";
import Questionnaire, { initialContext } from "./Questionnaire";
import Auth from "./Auth";
import Admin from "./Admin";
import Preferences from "./Preferences";
import { ContentDetails } from "./Activity";
import SingleSuggestion from "./SingleSuggestion";
import { Button, Empty, Note } from "./ui";
import Icon from "./Icon";
import Pwa from "./Pwa";

// type View =
//   | "home"
//   | "auth"
//   | "questions"
//   | "results"
//   | "detail"
//   | "active"
//   | "complete"
//   | "saved"
//   | "journey"
//   | "settings"
//   | "admin";
const dimensionNames: Record<string, string> = {
  detachment: "فاصله از روزمرگی",
  relaxation: "یه مکث آروم",
  autonomy: "به سلیقهٔ خودت",
  mastery: "یه چیز تازه",
  meaning: "یه لحظهٔ باارزش",
  affiliation: "کنار هم",
};

export default function Funilo() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const view = viewFromPathname(pathname);
  const authMode = authModeFromPathname(pathname);

  const resetToken =
    pathname === paths.reset ? searchParams.get("token") : null;

  const dispatch = useAppDispatch();
  const client = useMemo(() => createApiClient(dispatch), [dispatch]);
  const user = useAppSelector((state) => state.auth.user);
  const savedQuery = useGetSavedQuery(undefined, { skip: !user });

  const preferencesQuery = useGetPreferencesQuery(undefined, { skip: !user });

  const saved = savedQuery.data?.items ?? [];
  const preferences = preferencesQuery.data ?? null;

  const [boot, setBoot] = useState(true);
  const [context, setContext] = useState<Context>(initialContext);
  const [slate, setSlate] = useState<Slate | null>(null);
  const [detail, setDetail] = useState<Revision | null>(null);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [experience, setExperience] = useState<Experience | null>(null);
  const [award, setAward] = useState<Award | null>(null);
  const [journey, setJourney] = useState<Journey | null>(null);
  const [history, setHistory] = useState<Experience[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [feedbackDone, setFeedbackDone] = useState(false);

  const [routeLoading, setRouteLoading] = useState(false);

  const [authState, setAuthState] = useState<
    "checking" | "guest" | "authenticated" | "unavailable"
  >("checking");

  const main = useRef<HTMLElement>(null);
  const lock = useRef(false);
  const checkIn = useRef<{ fingerprint: string; id: string } | null>(null);

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
    setJourney(null);
    setHistory([]);
    checkIn.current = null;
  }, []);
  const report = useCallback(
    (e: unknown) => {
      setError(
        e instanceof Error ? e.message : "یه مشکلی پیش اومد؛دوباره امتحان کن.",
      );
      if (e instanceof ApiError && e.status === 401) {
        dispatch(clearUser());
        dispatch(apiSlice.util.resetApiState());
        clearPrivateState();

        setAuthState("guest");
        router.replace(paths.login);
      }
    },
    [dispatch, clearPrivateState, router],
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
    for (const queryError of [savedQuery.error, preferencesQuery.error]) {
      if (queryError && "status" in queryError && queryError.status === 401) {
        report(toApiError(queryError));
        break;
      }
    }
  }, [savedQuery.error, preferencesQuery.error, report]);

  useEffect(() => {
    let cancelled = false;

    const initialize = async () => {
      try {
        await refreshCsrf();

        const current = await client.getMe();

        if (cancelled) return;

        dispatch(setUser(current));
        setAuthState("authenticated");

        const active = await client.getActiveExperience();

        if (cancelled) return;

        setExperience(active.experience);
      } catch (e) {
        if (cancelled) return;

        if (e instanceof ApiError && e.status === 401) {
          dispatch(clearUser());
          setAuthState("guest");
        } else {
          setAuthState("unavailable");
          setError(
            e instanceof Error ? e.message : "امکان بررسی نشست وجود ندارد.",
          );
        }
      } finally {
        if (!cancelled) {
          setBoot(false);
        }
      }
    };

    void initialize();

    return () => {
      cancelled = true;
    };
  }, [client, dispatch]);

  // Load route-specific data on refresh,
  // browser Back/Forward, and direct navigation.
  useEffect(() => {
    if (boot) return;

    setRouteLoading(false);

    if (authState === "unavailable") return;

    if (!user) {
      if (!isAuthPath(pathname)) {
        const query = searchParams.toString();

        const destination = pathname + (query ? `?${query}` : "");

        router.replace(
          `${paths.login}?next=${encodeURIComponent(destination)}`,
        );
      }

      return;
    }

    if (isAuthPath(pathname) && pathname !== paths.reset) {
      router.replace(safeNextPath(searchParams.get("next")) ?? paths.discover);
      return;
    }

    if (pathname === paths.reset && !resetToken) {
      router.replace(paths.login);
      return;
    }

    if (view === "admin" && user.role === "user") {
      router.replace(paths.discover);
      return;
    }

    let cancelled = false;

    const loadRoute = async () => {
      const needsLoading = [
        "results",
        "detail",
        "active",
        "journey",
        "complete",
      ].includes(view);

      if (!needsLoading) return;

      setRouteLoading(true);

      try {
        if (view === "results") {
          const slateId = searchParams.get("slate");

          if (!slateId) {
            router.replace(paths.questions);
            return;
          }

          const session = await client.getSession(slateId);

          if (!cancelled) {
            setSlate(session);
          }
        }

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

        if (view === "journey") {
          const [journeyData, historyData] = await Promise.all([
            client.getJourney(),
            client.getExperienceHistory(),
          ]);

          if (!cancelled) {
            setJourney(journeyData);
            setHistory(historyData.items);
          }
        }

        if (view === "complete" && !award) {
          // The existing API does not expose
          // a completion-award recovery endpoint.
          router.replace(paths.journey);
        }
      } catch (e) {
        if (!cancelled) {
          report(e);
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
    boot,
    authState,
    user,
    pathname,
    searchParams,
    view,
    client,
    router,
    report,
    award,
    resetToken,
  ]);

  useEffect(() => {
    const heading = main.current?.querySelector("h1");
    if (heading) {
      heading.setAttribute("tabindex", "-1");
      heading.focus({ preventScroll: true });
    }
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [view, routeLoading, boot]);

  const finishLogin = async (email: string, password: string) => {
    const response = await client.login({
      email,
      password,
    });

    // Prevent cross-account cached data.
    dispatch(apiSlice.util.resetApiState());
    clearPrivateState();

    dispatch(setUser(response.user));
    setAuthState("authenticated");

    try {
      const { experience: activeExperience } =
        await client.getActiveExperience();

      setExperience(activeExperience);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        dispatch(clearUser());
        setAuthState("guest");
        throw e;
      }

      setError("ورود انجام شد، اما بررسی تجربهٔ فعال ناموفق بود.");
    }

    router.replace(safeNextPath(searchParams.get("next")) ?? paths.discover);
  };

  const login = (email: string, password: string) =>
    run(() => finishLogin(email, password));
  const recommend = () =>
    run(async () => {
      const fingerprint = JSON.stringify(context);
      if (!checkIn.current || checkIn.current.fingerprint !== fingerprint) {
        const check = await client.createCheckIn(context);
        checkIn.current = { fingerprint, id: check.id };
      }
      const result = await client.createSession({
        check_in_id: checkIn.current.id,
      });
      setSlate(result);

      router.push(`/individual/results?slate=${encodeURIComponent(result.id)}`);
    });

  const open = (item: Slot) =>
    run(async () => {
      if (!item.revision_id) {
        throw new Error("شناسهٔ نسخهٔ پیشنهاد موجود نیست.");
      }

      if (!slate) {
        throw new Error("جلسهٔ پیشنهاد معتبر پیدا نشد.");
      }

      setDetail(await client.getRevision(item.revision_id));

      setSlot(item);

      const params = new URLSearchParams({
        from: "individual",
        slate: slate.id,
        slot: item.slot_id,
      });

      router.push(
        `/activities/${encodeURIComponent(item.revision_id)}?${params.toString()}`,
      );
    });

  const replace = (item: Slot) =>
    run(async () => {
      let result: ReplacementState & {
        session_version: number;
        item: Slot;
        replaced: boolean;
      };
      try {
        result = await client.replaceSuggestion({
          sessionId: slate!.id,
          slotId: item.slot_id,
          expected_version: slate!.version,
        });
      } catch (e) {
        if (
          e instanceof ApiError &&
          [
            "VERSION_CONFLICT",
            "REPLACEMENT_LIMIT",
            "HISTORY_NOT_AT_END",
          ].includes(e.code)
        ) {
          setSlate(await client.getSession(slate!.id));
        }
        throw e;
      }
      const items = slate!.items.map((i) =>
        i.slot_id === item.slot_id ? result.item : i,
      );
      const n = items.filter((i) => !i.unavailable).length;
      setSlate({
        ...slate!,
        version: result.session_version,
        items,
        result_count: n,
        partial: n === 0,
        replacement_count: result.replacement_count,
        replacement_limit: result.replacement_limit,
        replacements_remaining: result.replacements_remaining,
        replacement_available: result.replacement_available,
        suggestion_index: result.suggestion_index,
        suggestion_count: result.suggestion_count,
      });
      if (!result.replaced)
        setNotice(
          "فعلاً گزینهٔ تازه‌ای با همین شرایط نداریم. سهمیهٔ تعویضت مصرف نشد.",
        );
    });
  const browse = (direction: "previous" | "next") =>
    run(async () => {
      try {
        setSlate(
          await client.navigateSession({
            sessionId: slate!.id,
            direction,
            expected_version: slate!.version,
          }),
        );
      } catch (e) {
        if (
          e instanceof ApiError &&
          ["VERSION_CONFLICT", "HISTORY_BOUNDARY"].includes(e.code)
        ) {
          setSlate(await client.getSession(slate!.id));
        }
        throw e;
      }
    });
  const toggleSave = (activityId: string) =>
    run(async () => {
      const exists = saved.some((s) => s.activity_id === activityId);

      if (exists) {
        await client.removeSaved(activityId);
      } else {
        await client.saveActivity(activityId);
      }

      setNotice(exists ? "از ذخیره‌ها برداشته شد." : "برای بعد نگهش داشتیم.");
    });

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
    checkIn.current = null;
    route("questions");
  };

  const summary = slate?.context_summary ?? context;
  return (
    <>
      <a className="skip-link" href="#main">
        رفتن به محتوای اصلی
      </a>
      <div className="demo-bar">
        <span className="status-dot" />
        نسخهٔ آزمایشی محلی{" "}
        <span className="demo-detail">· تجربه‌های تألیفی برای امتحان‌کردن</span>
      </div>
      <header className="site-header">
        <Link
          className="wordmark"
          href={user ? paths.discover : paths.landing}
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
          {experience?.status === "active" && (
            <button
              className="active-link"
              onClick={() => {
                if (experience) {
                  router.push(
                    `/experiences/${encodeURIComponent(experience.id)}`,
                  );
                }
              }}
            >
              <span className="status-dot" />
              تجربهٔ بازت
            </button>
          )}
          {user ? (
            <>
              <button
                className="account-button"
                onClick={() => route("settings")}
                aria-label="تنظیمات حساب"
              >
                <Icon name="user" size={19} />
                <span>{user.display_name || "حساب من"}</span>
              </button>
              {user.role !== "user" && (
                <button className="text-button" onClick={() => route("admin")}>
                  کارگاه محتوا
                </button>
              )}
            </>
          ) : (
            <button className="header-login" onClick={() => route("questions")}>
              <Icon name="user" size={17} />
              ورود <span className="login-extra">/ ساخت حساب</span>
            </button>
          )}
        </div>
      </header>
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

        {authState === "unavailable" && (
          <div className="error-banner" role="alert">
            <p>
              بررسی نشست امکان‌پذیر نبود. اتصال سرور را بررسی کن و دوباره تلاش
              کن.
            </p>

            <Button onClick={() => window.location.reload()}>
              تلاش دوباره
            </Button>
          </div>
        )}

        {boot ||
        routeLoading ||
        (authState === "guest" && !isAuthPath(pathname)) ||
        (authState === "authenticated" &&
          isAuthPath(pathname) &&
          pathname !== paths.reset) ? (
          <div className="loading-state" role="status">
            <span className="loading-flower" aria-hidden="true">
              <Icon name="spark" size={42} />
            </span>
            <p>یه لحظه، داریم آماده می‌شیم…</p>
          </div>
        ) : (
          <>
            {view === "discover" && (
              <section className="discover-intro">
                <span className="eyebrow">خانهٔ کشف فعالیت‌ها</span>

                <h1>دنیایی از تجربه‌های کوچیک در راهه.</h1>

                <p className="intro">
                  اینجا به‌زودی می‌تونی فعالیت‌های مختلف رو مرور کنی و چیزی که
                  به سلیقه‌ات نزدیکه پیدا کنی.
                </p>

                {experience?.status === "active" && (
                  <Button
                    secondary
                    onClick={() =>
                      router.push(
                        `/experiences/${encodeURIComponent(experience.id)}`,
                      )
                    }
                  >
                    ادامهٔ فعالیت قبلی
                  </Button>
                )}

                <div className="inline-actions wrap">
                  <Button onClick={() => route("questions")}>
                    پیشنهاد برای همین الان
                  </Button>

                  <Button secondary onClick={() => route("saved")}>
                    فعالیت‌های ذخیره‌شده
                  </Button>
                </div>
              </section>
            )}

            {view === "auth" && (
              <Auth
                mode={authMode}
                onModeChange={(mode) => {
                  const destination =
                    mode === "signup"
                      ? paths.signup
                      : mode === "forgot"
                        ? paths.forgot
                        : paths.login;

                  const next = safeNextPath(searchParams.get("next"));

                  router.push(
                    next
                      ? `${destination}?next=${encodeURIComponent(next)}`
                      : destination,
                  );
                }}
                busy={busy}
                resetToken={!!resetToken}
                login={login}
                forgot={async (email) => {
                  let ok = false;
                  await run(async () => {
                    await client.forgotPassword(email);
                    ok = true;
                  });
                  return ok;
                }}
                reset={(password) =>
                  run(async () => {
                    await client.resetPassword({
                      token: resetToken,
                      new_password: password,
                    });

                    dispatch(clearUser());
                    dispatch(apiSlice.util.resetApiState());
                    clearPrivateState();

                    setAuthState("guest");
                    router.replace(paths.login);

                    setNotice("رمزت عوض شد؛با رمز تازه وارد شو.");
                  })
                }
                signup={(email, password, name) =>
                  run(async () => {
                    await client.signup({
                      email,
                      password,
                      display_name: name,
                      adult_confirmed: true,
                    });
                    await finishLogin(email, password);
                  })
                }
              />
            )}
            {view === "questions" && (
              <Questionnaire
                value={context}
                defaults={preferences?.preferences}
                change={(v) => {
                  setContext(v);
                  checkIn.current = null;
                }}
                submit={recommend}
                busy={busy}
              />
            )}
            {view === "results" && slate && (
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
                    className="text-button"
                    disabled={busy}
                    onClick={returnHome}
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
                        any: "هر جا شد",
                      }[summary.venue]
                    }
                  </span>
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
                  saved={saved.some(
                    (s) => s.activity_id === slate.items[0]?.activity_id,
                  )}
                  open={open}
                  save={(item) => {
                    if (!item.activity_id) {
                      setError("شناسهٔ فعالیت موجود نیست.");
                      return;
                    }

                    void toggleSave(item.activity_id);
                  }}
                  replace={replace}
                  browse={browse}
                  changeConditions={returnHome}
                />
              </section>
            )}
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
                      router.push(paths.discover);
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
                      شروع مستقیم از خانه و ذخیره‌ها به تغییر قرارداد Backend
                      نیاز داره.
                    </Note>
                    <Button onClick={returnHome}>
                      برای الان پیشنهاد بگیرم
                    </Button>
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
            {view === "saved" && (
              <section>
                <span className="eyebrow">برای یه وقت دیگه</span>
                <h1>چیزهایی که نگه داشتی.</h1>
                <p className="intro">لازم نیست نوبتشون همین امروز باشه.</p>
                {savedQuery.isLoading ? (
                  <p role="status">در حال دریافت ذخیره‌ها…</p>
                ) : savedQuery.isError ? (
                  <div role="alert">
                    <p>دریافت ذخیره‌ها انجام نشد.</p>

                    <Button secondary onClick={() => void savedQuery.refetch()}>
                      تلاش دوباره
                    </Button>
                  </div>
                ) : saved.length === 0 ? (
                  <Empty title="اینجا هنوز خلوت و آرومه.">
                    <p>هر پیشنهادی دوست داشتی،برای بعد نگهش دار.</p>
                    <Button onClick={returnHome}>یه پیشنهاد ببینم</Button>
                  </Empty>
                ) : (
                  <div className="saved-list">
                    {saved.map((s) => (
                      <article className="saved-card" key={s.activity_id}>
                        <div>
                          <h2>
                            {s.unavailable
                              ? "فعلاً در دسترس نیست"
                              : s.content?.title}
                          </h2>
                          <p className="muted">{s.content?.teaser}</p>
                        </div>
                        <div className="inline-actions">
                          <Button
                            secondary
                            disabled={busy || s.unavailable || !s.revision_id}
                            onClick={() =>
                              run(async () => {
                                if (!s.revision_id) {
                                  throw new Error(
                                    "شناسهٔ نسخهٔ ذخیره‌شده موجود نیست.",
                                  );
                                }

                                setDetail(
                                  await client.getRevision(s.revision_id),
                                );

                                setSlot(null);

                                router.push(
                                  `/activities/${encodeURIComponent(s.revision_id)}?from=saved`,
                                );
                              })
                            }
                          >
                            ببینمش
                          </Button>
                          <button
                            className="text-button"
                            disabled={busy}
                            onClick={() => toggleSave(s.activity_id)}
                          >
                            بردار
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            )}
            {view === "journey" && journey && (
              <section>
                <span className="eyebrow">با ریتم خودت</span>
                <h1>مسیر کوچیک تو.</h1>
                <p className="intro">
                  اینجا خبری از عقب‌افتادن نیست.فقط لحظه‌هایی که برای خودت
                  ساختی.
                </p>
                {preferences?.preferences.show_gamification !== false && (
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
                    <div className="badge-list">
                      {journey.badges.map((key) => (
                        <span key={key} className="earned-badge">
                          ✧ {badgeNames[key]}
                        </span>
                      ))}
                    </div>

                    <div className="dimension-list">
                      {journey.completed_dimensions.map((key) => (
                        <span key={key}>{dimensionNames[key] ?? key}</span>
                      ))}
                    </div>
                  </>
                )}
                <h2 className="history-title">لحظه‌های قبلی</h2>
                {history.length ? (
                  <div className="history-list">
                    {history.map((e) => (
                      <article key={e.id}>
                        <span aria-hidden="true">
                          {e.status === "completed" ? "✧" : "◌"}
                        </span>
                        <div>
                          <h3>
                            {e.unavailable
                              ? "تجربهٔ کنارگذاشته‌شده"
                              : e.content_snapshot?.title}
                          </h3>
                          <p className="hint">
                            {new Intl.DateTimeFormat("fa-IR", {
                              dateStyle: "medium",
                            }).format(new Date(e.started_at))}{" "}
                            ·{" "}
                            {
                              {
                                active: "در جریان",
                                completed: "تموم‌شده",
                                cancelled: "لغوشده",
                                expired: "بسته‌شده",
                              }[e.status]
                            }
                          </p>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <Empty title="اولین لحظه هنوز در راهه.">
                    <p>هر وقت دلت خواست،یه تجربهٔ کوچیک انتخاب کن.</p>
                    <Button onClick={returnHome}>بریم انتخاب کنیم</Button>
                  </Empty>
                )}
              </section>
            )}
            {view === "settings" && (
              <>
                {preferencesQuery.isLoading ? (
                  <p role="status">در حال دریافت تنظیمات…</p>
                ) : preferencesQuery.isError ? (
                  <div role="alert">
                    <p>دریافت تنظیمات انجام نشد.</p>

                    <Button
                      secondary
                      onClick={() => void preferencesQuery.refetch()}
                    >
                      تلاش دوباره
                    </Button>
                  </div>
                ) : preferences ? (
                  <Preferences
                    key={preferences.version}
                    initial={preferences}
                    busy={busy}
                    save={(v) =>
                      run(async () => {
                        await client.updatePreferences(v);

                        checkIn.current = null;

                        setNotice("انتخاب‌هات نگه داشته شد.");
                      })
                    }
                  />
                ) : null}

                <div className="account-footer">
                  <p className="hint">{user?.email}</p>
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() =>
                      run(async () => {
                        await client.logout();
                        dispatch(clearUser());
                        dispatch(apiSlice.util.resetApiState());
                        clearPrivateState();

                        setAuthState("guest");
                        router.replace(paths.landing);
                      })
                    }
                  >
                    خروج از حساب
                  </button>
                </div>
              </>
            )}
            {view === "admin" && user && <Admin user={user} report={report} />}
          </>
        )}
      </main>

      {user && (
        <nav className="bottom-nav" aria-label="صفحه‌های اصلی">
          <button
            aria-current={view === "discover" ? "page" : undefined}
            onClick={() => route("discover")}
          >
            <Icon name="leaf" />
            کشف
          </button>

          <button
            aria-current={
              ["questions", "results", "detail", "active", "complete"].includes(
                view,
              )
                ? "page"
                : undefined
            }
            onClick={returnHome}
          >
            <Icon name="spark" />
            Individual
          </button>

          <button
            aria-current={view === "saved" ? "page" : undefined}
            onClick={() => route("saved")}
          >
            <Icon name="bookmark" />
            ذخیره‌ها
          </button>

          <button
            aria-current={view === "journey" ? "page" : undefined}
            onClick={() => route("journey")}
          >
            <Icon name="journey" />
            مسیر من
          </button>
        </nav>
      )}

      <footer className={`site-footer ${user ? "with-navigation" : ""}`}>
        <span className="footer-brand">
          مودیگو <span>· با ریتم تو</span>
        </span>
        <span>یه کم وقت برای خودت، بدون باید.</span>
        <span className="footer-local">نسخهٔ آزمایشی</span>
      </footer>
    </>
  );
}
