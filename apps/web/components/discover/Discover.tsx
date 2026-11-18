"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { number } from "@/lib/api";
import { useAuth } from "@/lib/hooks/useAuth";
import { paths } from "@/lib/navigation";
import { apiSlice } from "@/lib/store/api/apiSlice";
import { toApiError } from "@/lib/store/api/baseQuery";

import Icon from "../Icon";
import MomentArt from "../MomentArt";
import styles from "./Discover.module.css";

const categories = new Map([
  ["detachment", "فاصله از روزمرگی"],
  ["relaxation", "آرامش"],
  ["autonomy", "انتخاب آزاد"],
  ["mastery", "یادگیری و مهارت"],
  ["meaning", "کارهای معنادار"],
  ["affiliation", "وقت گذراندن با دیگران"],
]);

const pageSize = 30;

function normalize(value: string) {
  return value
    .normalize("NFKC")
    .replace(/ي/g, "ی")
    .replace(/ك/g, "ک")
    .replace(/[\s\u200c]+/g, " ")
    .trim();
}

export default function Discover() {
  const { user } = useAuth();
  const params = useSearchParams();
  const query = params.get("q") ?? "";
  const category = params.get("tag") ?? "";
  const requestedLimit = Number(params.get("limit"));
  const limit = Number.isSafeInteger(requestedLimit)
    ? Math.max(pageSize, requestedLimit)
    : pageSize;

  const catalog = apiSlice.endpoints.getDiscover.useQuery(undefined, {
    skip: !user,
    refetchOnMountOrArgChange: true,
  });
  const saved = apiSlice.endpoints.getSaved.useQuery(undefined, {
    skip: !user,
  });
  const active = apiSlice.endpoints.getActiveExperience.useQuery(undefined, {
    skip: !user,
  });
  const [save, saving] = apiSlice.endpoints.saveActivity.useMutation();
  const [remove, removing] = apiSlice.endpoints.removeSaved.useMutation();
  const [notice, setNotice] = useState("");

  if (!user) return null;

  const term = normalize(query);
  const activities = catalog.isError || catalog.isFetching ? [] : (catalog.data?.items ?? []);
  const results = activities.filter(({ title, primary_dimension: dimension }) => {
    const label = categories.get(dimension) ?? "";

    return (
      (!category || dimension === category) &&
      normalize(`${title} ${label}`).includes(term)
    );
  });
  const savedIds = new Set(saved.data?.items.map((item) => item.activity_id));

  function updateFilter(key: string, value: string) {
    const url = new URL(window.location.href);

    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);

    if (key !== "limit") url.searchParams.delete("limit");

    window.history.replaceState(null, "", url);
  }

  async function toggle(id: string, exists: boolean) {
    try {
      await (exists ? remove(id) : save(id)).unwrap();
      setNotice(exists ? "از ذخیره‌ها حذف شد." : "برای بعد ذخیره شد.");
    } catch (error) {
      setNotice(toApiError(error).message);
    }
  }

  return (
    <main id="main" className={`page-shell ${styles.feed}`}>
      <header className={styles.heading}>
        <h1>کشف فعالیت‌ها</h1>
        <Link href={paths.questions}>
          <Icon name="spark" size={18} /> پیشنهاد برای همین الان
        </Link>
        <Link href={paths.saved}>فعالیت‌های ذخیره‌شده</Link>
        {active.data?.experience?.status === "active" && (
          <Link
            href={`/experiences/${encodeURIComponent(active.data.experience.id)}`}
          >
            ادامهٔ فعالیت قبلی
          </Link>
        )}
      </header>

      <input
        className={styles.search}
        type="search"
        aria-label="جست‌وجوی فعالیت"
        placeholder="دنبال چه فعالیتی می‌گردی؟"
        value={query}
        onChange={(event) => updateFilter("q", event.target.value)}
      />

      <div className={styles.chips} role="group" aria-label="دسته‌بندی فعالیت">
        <button
          aria-pressed={!category}
          onClick={() => updateFilter("tag", "")}
        >
          همه
        </button>
        {Array.from(categories, ([key, label]) => (
          <button
            key={key}
            aria-pressed={category === key}
            onClick={() => updateFilter("tag", key)}
          >
            {label}
          </button>
        ))}
      </div>

      {catalog.isFetching ? (
        <p role="status">در حال دریافت فعالیت‌ها…</p>
      ) : catalog.isError ? (
        <p role="alert">
          فعالیت‌ها دریافت نشد.{" "}
          <button onClick={catalog.refetch}>تلاش دوباره</button>
        </p>
      ) : catalog.isSuccess && (
        <p role="status">
          {results.length
            ? `${number(results.length)} فعالیت`
            : "فعالیتی پیدا نشد."}
        </p>
      )}

      {saved.isError && (
        <p role="alert">
          ذخیره‌ها دریافت نشد.{" "}
          <button onClick={saved.refetch}>تلاش دوباره</button>
        </p>
      )}
      <span role="status">{notice}</span>

      <div className={styles.grid}>
        {results.slice(0, limit).map((activity) => {
          const exists = savedIds.has(activity.activity_id);
          const detail = new URLSearchParams({
            from: "discover",
            filters: params.toString(),
          });

          return (
            <article className={styles.card} key={activity.activity_id}>
              <Link
                prefetch={false}
                href={`/activities/${encodeURIComponent(activity.revision_id)}?${detail}`}
              >
                <div className={styles.cover}>
                  <MomentArt
                    variant={activity.primary_dimension === "mastery" ? 2 : 0}
                  />
                </div>
                <div className={styles.copy}>
                  <small>{categories.get(activity.primary_dimension)}</small>
                  <h2>{activity.title}</h2>
                </div>
              </Link>

              <div className={styles.actions}>
                <button
                  aria-pressed={exists}
                  aria-label={`${exists ? "حذف از ذخیره‌ها" : "ذخیره برای بعد"}، ${activity.title}`}
                  disabled={
                    !saved.data ||
                    saved.isFetching ||
                    saving.isLoading ||
                    removing.isLoading
                  }
                  onClick={() => toggle(activity.activity_id, exists)}
                >
                  <Icon name="bookmark" size={16} />
                  {exists ? "ذخیره‌شده" : "ذخیره برای بعد"}
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {results.length > limit && (
        <p>
          <button
            className="text-button"
            onClick={() => updateFilter("limit", String(limit + pageSize))}
          >
            نمایش فعالیت‌های بیشتر
          </button>
        </p>
      )}
    </main>
  );
}
