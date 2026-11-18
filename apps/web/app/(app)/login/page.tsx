import type { Metadata } from "next";
import AuthPage from "@/components/auth/AuthPage";

export const metadata: Metadata = {
  title: "ورود | مودیگو",
};

export default function Page() {
  return <AuthPage />;
}
