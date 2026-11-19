"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { number } from "@/lib/api";
import { useAuth } from "@/lib/hooks/useAuth";
import { apiSlice } from "@/lib/store/api/apiSlice";
import { toApiError } from "@/lib/store/api/baseQuery";
import type { DiscoverItem } from "@/types";

import Icon, { type IconName } from "../Icon";
import { updateDiscoverFilter } from "./discoverFilters";
import styles from "./Discover.module.css";

const categories = new Map<string, { label: string; icon: IconName }>([
  ["detachment", { label: "فاصله از روزمرگی", icon: "leaf" }],
  ["relaxation", { label: "آرامش", icon: "coffee" }],
  ["autonomy", { label: "انتخاب آزاد", icon: "spark" }],
  ["mastery", { label: "یادگیری و مهارت", icon: "book" }],
  ["meaning", { label: "کارهای معنادار", icon: "heart" }],
  ["affiliation", { label: "وقت گذراندن با دیگران", icon: "users" }],
]);

type DiscoverFilter = {
  label: string;
  icon: IconName;
  matches: (activity: DiscoverItem, saved: ReadonlySet<string>) => boolean;
};

const filters = new Map<string, DiscoverFilter>([
  ["", { label: "همه", icon: "dashboard", matches: () => true }],
  ...Array.from(categories, ([key, category]): [string, DiscoverFilter] => [
    key, { ...category, matches: (activity) => activity.primary_dimension === key },
  ]),
  ["home", { label: "در خانه", icon: "home", matches: (activity) => activity.venue === "home" }],
  ["outdoor", { label: "فضای باز", icon: "sun", matches: (activity) => activity.venue === "outdoor" }],
  ["indoor_public", { label: "سرپوشیده", icon: "building", matches: (activity) => activity.venue === "indoor_public" }],
  ["named_place", { label: "مکان مشخص", icon: "pin", matches: (activity) => Boolean(activity.place) }],
  ["saved", { label: "ذخیره‌شده‌ها", icon: "bookmark", matches: (activity, saved) => saved.has(activity.activity_id) }],
]);

const pageSize = 30;
const venueLabels = {
  home: "در خانه",
  outdoor: "فضای باز",
  indoor_public: "فضای عمومی سرپوشیده",
};

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
  const requestedFilter = params.get("tag") ?? "";
  const selectedFilter = filters.has(requestedFilter) ? requestedFilter : "";
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
  const [save, saving] = apiSlice.endpoints.saveActivity.useMutation();
  const [remove, removing] = apiSlice.endpoints.removeSaved.useMutation();
  const [notice, setNotice] = useState("");

  if (!user) return null;

  const term = normalize(query);
  const savedIds = new Set(saved.data?.items.map((item) => item.activity_id));
  const filter = filters.get(selectedFilter);
  const activities = catalog.isError || catalog.isFetching ? [] : (catalog.data?.items ?? []);
  const results = activities.filter((activity) => {
    const label = categories.get(activity.primary_dimension)?.label ?? "";
    return (!filter || filter.matches(activity, savedIds)) &&
      normalize(`${activity.title} ${label}`).includes(term);
  });

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
      <h1 className="sr-only">کشف فعالیت‌ها</h1>
      <div className={styles.chips} role="group" aria-label="فیلتر فعالیت‌ها">
        {Array.from(filters, ([key, { label, icon }]) => (
          <button
            key={key}
            type="button"
            aria-pressed={selectedFilter === key}
            onClick={() => updateDiscoverFilter("tag", key)}
          >
            <span className={styles.filterIcon}><Icon name={icon} size={18} /></span>
            {label}
          </button>
        ))}
      </div>

      {catalog.isFetching || (selectedFilter === "saved" && saved.isFetching) ? (
        <p role="status">در حال دریافت فعالیت‌ها…</p>
      ) : catalog.isError ? (
        <p role="alert">
          فعالیت‌ها دریافت نشد.{" "}
          <button onClick={catalog.refetch}>تلاش دوباره</button>
        </p>
      ) : catalog.isSuccess && (selectedFilter !== "saved" || !saved.isError) && (
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
          const description = activity.teaser?.trim();
          const location = activity.place
            ? [activity.place.name, activity.place.city].filter(Boolean).join("، ")
            : activity.venue && venueLabels[activity.venue];
          const detail = new URLSearchParams({
            from: "discover",
            filters: params.toString(),
          });

          return (
            <article className={styles.card} key={activity.activity_id}>
              <div className={styles.cardHeader}>
                <span className={styles.category} data-dimension={activity.primary_dimension}>
                  {categories.get(activity.primary_dimension)?.label}
                </span>
                <button
                  type="button"
                  className={styles.bookmark}
                  aria-pressed={exists}
                  aria-label={`ذخیره برای بعد، ${activity.title}`}
                  title={exists ? "حذف از ذخیره‌ها" : "ذخیره برای بعد"}
                  disabled={
                    !saved.data ||
                    saved.isFetching ||
                    saving.isLoading ||
                    removing.isLoading
                  }
                  onClick={() => toggle(activity.activity_id, exists)}
                >
                  <Icon name="bookmark" size={19} />
                </button>
              </div>
              <h2>{activity.title}</h2>
              {description && <p className={styles.description}>{description}</p>}
              <div className={styles.cardFooter}>
                {location && (
                  <span className={styles.location}>
                    <Icon name="pin" size={18} />
                    <span>{location}</span>
                  </span>
                )}
                <Link
                  className={styles.details}
                  aria-label={`جزئیات ${activity.title}`}
                  prefetch={false}
                  href={`/activities/${encodeURIComponent(activity.revision_id)}?${detail}`}
                >
                  جزئیات <Icon name="arrow" size={16} />
                </Link>
              </div>
            </article>
          );
        })}
      </div>

      {results.length > limit && (
        <p>
          <button
            className="text-button"
            onClick={() => updateDiscoverFilter("limit", String(limit + pageSize))}
          >
            نمایش فعالیت‌های بیشتر
          </button>
        </p>
      )}
    </main>
  );
}
