import type { Metadata } from "next";

import IndividualResultsPage from "@/components/individual/IndividualResultsPage";

export const metadata: Metadata = {
  title: "پیشنهاد مخصوص تو | مودیگو",
  description: "پیشنهاد فعالیت متناسب با حال، وقت و شرایط فعلی.",
};

export default function Page() {
  return <IndividualResultsPage />;
}
