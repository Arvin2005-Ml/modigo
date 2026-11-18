import type { Metadata } from "next";

import Discover from "@/components/discover/Discover";

export const metadata: Metadata = {
  title: "کشف فعالیت‌ها | مودیگو",
};

export default function Page() {
  return <Discover />;
}
