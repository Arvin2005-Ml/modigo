import type { Metadata } from "next";

import SettingsPage from "@/components/settings/SettingsPage";

export const metadata: Metadata = {
  title: "تنظیمات | مودیگو",
  description: "مدیریت تنظیمات و انتخاب‌های حساب مودیگو.",
};

export default function Page() {
  return <SettingsPage />;
}
