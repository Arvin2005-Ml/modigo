"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { paths } from "@/lib/navigation";
import { useAppSelector } from "@/lib/store/hooks";

import Icon from "@/components/Icon";

export default function AppNavigation() {
  const pathname = usePathname();

  const user = useAppSelector((state) => state.auth.user);

  if (!user || pathname === paths.dashboard) {
    return null;
  }

  const isDiscover = pathname === paths.discover;

  const isIndividual =
    pathname === paths.questions || pathname.startsWith(`${paths.questions}/`);

  const isSaved = pathname === paths.saved;

  const isJourney = pathname === paths.journey;

  return (
    <nav className="bottom-nav" aria-label="صفحه‌های اصلی">
      <Link
        href={paths.discover}
        aria-current={isDiscover ? "page" : undefined}
      >
        <Icon name="leaf" />
        کشف
      </Link>

      <Link
        href={paths.questions}
        aria-current={isIndividual ? "page" : undefined}
      >
        <Icon name="spark" />
        Individual
      </Link>

      <Link href={paths.saved} aria-current={isSaved ? "page" : undefined}>
        <Icon name="bookmark" />
        ذخیره‌ها
      </Link>

      <Link href={paths.journey} aria-current={isJourney ? "page" : undefined}>
        <Icon name="journey" />
        مسیر من
      </Link>
    </nav>
  );
}
