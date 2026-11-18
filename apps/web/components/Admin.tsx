import { useEffect, useMemo, useRef, useState } from "react";

import type { User, AdminDraft, AdminActivity, AdminJob } from "@/types";

import { number } from "@/lib/api";
import { useAppDispatch } from "@/lib/store/hooks";
import { useGetAdminActivitiesQuery } from "@/lib/store/api/apiSlice";
import { createApiClient } from "@/lib/store/api/apiClient";
import { toApiError } from "@/lib/store/api/baseQuery";
import { Button } from "./ui";

const states: Record<string, string> = {
  draft: "پیش‌نویس",
  review: "منتظر بررسی",
  published: "منتشرشده",
  superseded: "نسخهٔ پیشین",
  archived: "کنارگذاشته‌شده",
  rejected: "برگشت‌خورده",
};

const dimensions: Record<string, string> = {
  detachment: "فاصله از روزمرگی",
  relaxation: "آرامش",
  autonomy: "انتخاب آزاد",
  mastery: "یادگیری",
  meaning: "معنا",
  affiliation: "ارتباط",
};

export default function Admin({
  user,
  report,
}: {
  user: User;
  report: (error: unknown) => void;
}) {
  const dispatch = useAppDispatch();

  const client = useMemo(() => createApiClient(dispatch), [dispatch]);

  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState("draft");

  const [selected, setSelected] = useState<AdminActivity | null>(null);

  const [draft, setDraft] = useState<AdminDraft | null>(null);

  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const [job, setJob] = useState<AdminJob | null>(null);

  const [reason, setReason] = useState("");
  const lock = useRef(false);
  const clearSelection = () => {
    setSelected(null);
    setDraft(null);
    setSource("");
  };

  const {
    currentData: list,
    error: listError,
    isFetching,
  } = useGetAdminActivitiesQuery({
    limit: 20,
    offset,
    state: filter,
  });

  useEffect(() => {
    if (listError) {
      report(toApiError(listError));
    }
  }, [listError, report]);

  // Poll admin jobs while they are running.
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.state)) {
      return;
    }

    const timer = setInterval(() => {
      client.getAdminJob(job.id).then(setJob).catch(report);
    }, 2000);

    return () => clearInterval(timer);
  }, [job, client, report]);

  const open = async (id: string) => {
    const activity = await client.getAdminActivity(id);

    const firstDraft = activity.revisions?.[0];
    if (!firstDraft) {
      throw new Error("برای این فعالیت نسخه‌ای پیدا نشد.");
    }

    setSelected(activity);
    setDraft(firstDraft);

    setSource(JSON.stringify(firstDraft.content, null, 2));

    setMessage("");
    setReason("");
  };

  const perform = async (action: () => Promise<void>) => {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setMessage("");

    try {
      await action();
    } catch (e) {
      report(e);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  };

  const action = (name: string) =>
    perform(async () => {
      if (!draft || !selected) return;

      const payload = {
        id: draft.id,
        expected_draft_version: draft.draft_version,
      };

      if (name === "publish") {
        await client.publishAdminRevision(payload);
      } else {
        await client.submitAdminRevision(payload);
      }

      await open(selected.id);

      setMessage(name === "publish" ? "نسخه منتشر شد." : "برای بررسی ثبت شد.");
    });

  return (
    <section className="admin-layout">
      <aside className="admin-sidebar">
        <span className="eyebrow">کارگاه محتوا</span>

        <h1>از ایده تا یه تجربه</h1>

        <p className="muted">
          ۴۵۰ بذر،هنوز محتوای آمادهٔ نمایش نیستن. نمونه‌های نمایشی هم تأیید
          انتشار عمومی ندارن.
        </p>

        <label className="label">
          وضعیت
          <select
            className="input"
            value={filter}
            disabled={busy}
            onChange={(e) => {
              setFilter(e.target.value);
              setOffset(0);
              clearSelection();
            }}
          >
            <option value="">همه</option>

            {Object.entries(states).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>

        {list && (
          <p className="hint">{number(list.total)} فعالیت در این فهرست</p>
        )}

        <div className="admin-items">
          {list?.items.map((activity) => (
            <button
              key={activity.id}
              aria-pressed={selected?.id === activity.id}
              className="admin-row"
              disabled={busy}
              onClick={() => perform(() => open(activity.id))}
            >
              <span>{activity.raw_title}</span>

              <small>{dimensions[activity.primary_dimension]}</small>
            </button>
          ))}
        </div>

        <div className="inline-actions">
          <Button
            secondary
            disabled={busy || isFetching || offset === 0}
            onClick={() => {
              setOffset(Math.max(0, offset - 20));
              clearSelection();
            }}
          >
            قبلی
          </Button>

          <Button
            secondary
            disabled={busy || isFetching || !list?.next_offset}
            onClick={() => {
              setOffset(list!.next_offset!);
              clearSelection();
            }}
          >
            بعدی
          </Button>
        </div>
      </aside>

      <div className="admin-editor">
        {selected && draft ? (
          <>
            <span className="eyebrow">
              {states[draft.state]} · نسخهٔ {number(draft.revision_number)}
            </span>

            <h2>{selected.raw_title}</h2>

            <p className="hint">
              منبع: <bdi>{selected.seed_key}</bdi> ·{" "}
              {draft.origin === "demo"
                ? "نمونهٔ نمایشی؛ تولید مدل نیست"
                : draft.origin === "ai"
                  ? "پیش‌نویس تولید مدل؛ نیازمند بازبینی"
                  : "ویرایش انسانی"}
            </p>

            <label className="label">
              نسخه
              <select
                className="input"
                value={draft.id}
                disabled={busy}
                onChange={(e) => {
                  const revision = selected.revisions!.find(
                    (r) => r.id === e.target.value,
                  )!;

                  setDraft(revision);
                  setSource(JSON.stringify(revision.content, null, 2));
                }}
              >
                {selected.revisions!.map((revision) => (
                  <option key={revision.id} value={revision.id}>
                    {number(revision.revision_number)} ·{" "}
                    {states[revision.state]}
                  </option>
                ))}
              </select>
            </label>

            {draft.content && (
              <div className="admin-preview">
                <span className="eyebrow">پیش‌نمایش کارت</span>

                <h3>{draft.content.title}</h3>

                <p>{draft.content.teaser}</p>

                <p>{draft.content.first_step}</p>
              </div>
            )}

            {!draft.content && (
              <p className="soft-note">
                این بذر هنوز پخته نشده. محتوای کامل قرارداد را در ویرایشگر وارد
                کن؛بدون محتوای معتبر قابل ارسال به بررسی نیست.
              </p>
            )}

            {["draft", "rejected"].includes(draft.state) && (
              <div className="soft-note">
                <p>
                  می‌تونی برای این بذر پیش‌نویس آماده کنی؛ پیش از انتشار حتماً
                  بررسی انسان لازمه.
                </p>

                <Button
                  secondary
                  disabled={
                    busy ||
                    !!(
                      job &&
                      job.activity_id === selected.id &&
                      ["queued", "running"].includes(job.state)
                    )
                  }
                  onClick={() =>
                    perform(async () => {
                      setJob(
                        await client.cookAdminActivity({
                          id: selected.id,
                          target_draft_id: draft.id,
                          expected_draft_version: draft.draft_version,
                          prompt_version: "cook_v1",
                          editor_constraints: "",
                        }),
                      );
                    })
                  }
                >
                  آماده‌کردن پیش‌نویس
                </Button>

                {job?.activity_id === selected.id && (
                  <div role="status">
                    <p>
                      {job.provider === "demo"
                        ? "نمونهٔ محلی؛ تولید مدل نیست. "
                        : "درخواست تولید محتوا. "}

                      {
                        (
                          {
                            queued: "در صف",
                            running: "در حال آماده‌سازی",
                            succeeded: "آماده برای بازبینی",
                            failed:
                              job.error_code === "DEMO_FIXTURE_UNAVAILABLE"
                                ? "برای این بذر نمونهٔ محلی نداریم."
                                : job.error_code === "STALE_DRAFT"
                                  ? "پیش‌نویس تغییر کرده؛ خروجی ذخیره نشد."
                                  : "آماده‌سازی انجام نشد؛ تنظیمات یا محتوای بذر را بررسی کن.",
                            cancelled: "لغو شد",
                          } as Record<string, string>
                        )[job.state]
                      }
                    </p>

                    {["queued", "running"].includes(job.state) && (
                      <Button
                        secondary
                        disabled={busy}
                        onClick={() =>
                          perform(async () =>
                            setJob(await client.cancelAdminJob(job.id)),
                          )
                        }
                      >
                        لغو
                      </Button>
                    )}

                    {job.state === "succeeded" && (
                      <Button
                        secondary
                        disabled={busy}
                        onClick={() => perform(() => open(selected.id))}
                      >
                        بارگذاری پیش‌نویس آماده
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )}

            <label className="label" htmlFor="content-json">
              محتوای کامل و شرایط اجرا
            </label>

            <p id="json-hint" className="hint">
              ویرایشگر موقت برای اپراتور فنی؛ فیلدها طبق قرارداد محتوا هستند.
              متن‌ها فارسی و شناسه‌های فنی انگلیسی بمانند.
            </p>

            <textarea
              id="content-json"
              aria-describedby="json-hint"
              className="input json-editor"
              dir="ltr"
              value={source}
              readOnly={busy || !["draft", "rejected"].includes(draft.state)}
              onChange={(e) => setSource(e.target.value)}
              spellCheck={false}
            />

            <div className="inline-actions wrap">
              {["draft", "rejected"].includes(draft.state) && (
                <>
                  <Button
                    disabled={busy}
                    onClick={() =>
                      perform(async () => {
                        let content: unknown;

                        try {
                          content = JSON.parse(source);
                        } catch {
                          throw new Error("ساختار JSON درست نیست.");
                        }

                        const revision = await client.updateAdminRevision({
                          id: draft.id,
                          expected_draft_version: draft.draft_version,
                          content,
                        });

                        setDraft(revision);
                        setSelected(
                          (current) =>
                            current && {
                              ...current,
                              revisions: current.revisions?.map((item) =>
                                item.id === revision.id ? revision : item,
                              ),
                            },
                        );

                        setSource(JSON.stringify(revision.content, null, 2));

                        setMessage("پیش‌نویس نگه داشته شد.");
                      })
                    }
                  >
                    ذخیرهٔ ویرایش
                  </Button>

                  <Button
                    secondary
                    disabled={busy || !draft.content}
                    onClick={() => action("submit")}
                  >
                    ارسال برای بررسی
                  </Button>
                </>
              )}

              {draft.state === "review" && user.role === "admin" && (
                <Button disabled={busy} onClick={() => action("publish")}>
                  بررسی کردم؛منتشر کن
                </Button>
              )}

              <Button
                secondary
                disabled={busy}
                onClick={() =>
                  perform(async () => {
                    await client.createAdminRevision({
                      id: selected.id,
                      source_revision_id: draft.id,
                    });

                    await open(selected.id);
                  })
                }
              >
                ساخت نسخهٔ تازه
              </Button>

              {user.role === "admin" &&
                (selected.active || selected.withdrawn) && (
                  <>
                    <label className="label">
                      دلیل تغییر وضعیت
                      <input
                        className="input"
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        minLength={5}
                        maxLength={240}
                      />
                    </label>

                    {selected.active ? (
                      <Button
                        secondary
                        disabled={busy || reason.trim().length < 5}
                        onClick={() =>
                          perform(async () => {
                            await client.withdrawAdminActivity({
                              id: selected.id,
                              reason,
                            });

                            await open(selected.id);

                            setMessage("محتوا از نمایش و شروع کنار گذاشته شد.");
                          })
                        }
                      >
                        کنارگذاشتن از نمایش
                      </Button>
                    ) : (
                      <Button
                        secondary
                        disabled={
                          busy ||
                          reason.trim().length < 5 ||
                          draft.state !== "published"
                        }
                        onClick={() =>
                          perform(async () => {
                            await client.reactivateAdminActivity({
                              id: selected.id,
                              reason,
                            });

                            await open(selected.id);

                            setMessage("محتوا دوباره فعال شد.");
                          })
                        }
                      >
                        فعال‌کردن نسخهٔ بازبینی‌شده
                      </Button>
                    )}
                  </>
                )}
            </div>

            <p role="status" className="success">
              {message}
            </p>
          </>
        ) : (
          <div className="empty-state">
            <h2>یه بذر انتخاب کن</h2>

            <p className="muted">
              عنوان خام،نسخه‌ها و وضعیت انتشارش رو اینجا می‌بینی.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
