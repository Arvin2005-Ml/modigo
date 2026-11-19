"use client";

import { useSearchParams } from "next/navigation";
import Icon from "../Icon";
import { updateDiscoverFilter } from "./discoverFilters";
import styles from "./Discover.module.css";

export default function DiscoverSearch() {
  const params = useSearchParams();

  return (
    <div className={styles.search} role="search">
      <Icon name="search" size={20} />
      <input
        type="search"
        aria-label="جست‌وجوی فعالیت"
        placeholder="جست‌وجوی فعالیت"
        value={params.get("q") ?? ""}
        onChange={(event) => updateDiscoverFilter("q", event.target.value)}
      />
    </div>
  );
}
