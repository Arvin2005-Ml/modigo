import type { Metadata } from "next";

import IndividualQuestionnairePage from "@/components/individual/IndividualQuestionnairePage";

export const metadata: Metadata = {
  title: "پیشنهاد برای همین الان | مودیگو",
  description: "با چند سؤال کوتاه، فعالیتی متناسب با وقت و شرایط خودت پیدا کن.",
};

export default function Page() {
  return <IndividualQuestionnairePage />;
}
