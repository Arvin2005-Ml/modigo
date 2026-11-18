export type AppView =
  | "dashboard"
  | "discover"
  | "auth"
  | "questions"
  | "results"
  | "detail"
  | "active"
  | "complete"
  | "saved"
  | "journey"
  | "settings"
  | "admin";

export type AuthMode = "login" | "signup" | "forgot";

export const paths = {
  landing: "/",
  dashboard: "/dashboard",
  discover: "/discover",
  questions: "/individual",
  results: "/individual/results",
  saved: "/saved",
  journey: "/journey",
  settings: "/settings",
  admin: "/admin",
  login: "/login",
  signup: "/signup",
  forgot: "/forgot-password",
  reset: "/reset-password",
} as const;

export function viewFromPathname(pathname: string): AppView {
  if (pathname === paths.dashboard) return "dashboard";
  if (pathname === paths.discover) return "discover";
  if (pathname === paths.questions) return "questions";
  if (pathname === paths.results) return "results";

  if (/^\/activities\/[^/]+$/.test(pathname)) {
    return "detail";
  }

  if (/^\/experiences\/[^/]+\/complete$/.test(pathname)) {
    return "complete";
  }

  if (/^\/experiences\/[^/]+$/.test(pathname)) {
    return "active";
  }

  if (pathname === paths.saved) return "saved";
  if (pathname === paths.journey) return "journey";
  if (pathname === paths.settings) return "settings";
  if (pathname === paths.admin) return "admin";

  return "auth";
}

export function isAuthPath(pathname: string): boolean {
  const authPaths: readonly string[] = [
    paths.login,
    paths.signup,
    paths.forgot,
    paths.reset,
  ];

  return authPaths.includes(pathname);
}

export function authModeFromPathname(pathname: string): AuthMode {
  if (pathname === paths.signup) return "signup";
  if (pathname === paths.forgot) return "forgot";
  return "login";
}

export function safeNextPath(next: string | null): string | null {
  if (
    !next ||
    !next.startsWith("/") ||
    next.startsWith("//") ||
    next.includes("\\")
  ) {
    return null;
  }

  try {
    const url = new URL(next, "https://moodigo.invalid");

    const allowed =
      /^(?:\/dashboard|\/discover|\/individual(?:\/results)?|\/activities\/[^/]+|\/experiences\/[^/]+(?:\/complete)?|\/saved|\/journey|\/settings|\/admin)$/;

    if (
      url.origin !== "https://moodigo.invalid" ||
      !allowed.test(url.pathname)
    ) {
      return null;
    }

    return url.pathname + url.search;
  } catch {
    return null;
  }
}
