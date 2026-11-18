import type { Metadata } from "next";

import JourneyPage from "@/components/journey/JourneyPage";

export const metadata: Metadata = {
  title: "مسیر من | مودیگو",
  description: "تجربه‌ها و لحظه‌هایی که برای خودت ساختی.",
};

export default function Page() {
  return <JourneyPage />;
}
