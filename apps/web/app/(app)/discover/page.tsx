import { readFile } from "node:fs/promises";
import { join } from "node:path";
import type { Metadata } from "next";

import Discover, {
  type DiscoverActivity,
} from "@/components/discover/Discover";

export const metadata: Metadata = {
  title: "کشف فعالیت‌ها | مودیگو",
};

type ExportedActivity = {
  id: string;
  raw_title: string;
  primary_dimension: string;
  active: boolean;
  published_revision_id: string | null;
};

export default async function Page() {
  const file = await readFile(
    join(process.cwd(), "activities(1).json"),
    "utf8",
  );
  const activities: DiscoverActivity[] = [];

  for (const line of file.split(/\r?\n/)) {
    if (!line.trim()) continue;

    const activity: ExportedActivity = JSON.parse(line.trim());

    if (activity.active !== true || !activity.published_revision_id) continue;

    activities.push({
      id: activity.id,
      title: activity.raw_title,
      dimension: activity.primary_dimension,
      revisionId: activity.published_revision_id,
    });
  }

  return <Discover activities={activities} />;
}
