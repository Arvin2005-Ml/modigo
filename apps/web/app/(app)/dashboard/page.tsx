import type { Metadata } from "next";

import DashboardPage from "@/components/dashboard/DashboardPage";

export const metadata: Metadata = { title: "پنل کاربری | مودیگو" };

export default function Page() {
  return <DashboardPage />;
}
