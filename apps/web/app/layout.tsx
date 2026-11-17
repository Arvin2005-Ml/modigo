import type { Metadata, Viewport } from "next";

import "./globals.css";
import "./brand.css";

import StoreProvider from "./StoreProviders";

export const metadata: Metadata = {
  title: "مودیگو — یه وقت کوچیک برای خودت",
  description: "چند پیشنهاد ساده برای وقت آزاد، با حال و شرایط خودت.",
  applicationName: "مودیگو",

  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "مودیگو",
  },

  icons: {
    icon: "/brand/moodigo-icon-256.png",
    apple: "/brand/moodigo-icon-512.png",
  },

  robots: {
    index: false,
    follow: false,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#F8F5EF",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fa" dir="rtl">
      <body>
        <StoreProvider>{children}</StoreProvider>
      </body>
    </html>
  );
}
