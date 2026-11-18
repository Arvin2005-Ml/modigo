import type { Metadata } from "next";

import SavedPage from "@/components/saved/SavedPage";

export const metadata: Metadata = {
  title: "فعالیت‌های ذخیره‌شده | مودیگو",
  description: "فعالیت‌هایی که برای تجربه‌کردن در آینده نگه داشته‌ای.",
};

export default function Page() {
  return <SavedPage />;
}
