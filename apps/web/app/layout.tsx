import type { Metadata, Viewport } from "next";

import "./globals.css";
import StoreProvider from "./StoreProviders";

export const metadata: Metadata = {
  title: "مودیگو — یه وقت کوچیک برای خودت",
  description: "چند پیشنهاد ساده برای وقت آزاد،با حال و شرایط خودت.",
  applicationName: "فانیلو",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "مودیگو",
  },
  icons: {
    icon: "/icons/icon.svg",
    apple: "/icons/apple-touch-icon.png",
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
  themeColor: "#f6f8f7",
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
