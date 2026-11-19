import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import Landing from "@/components/landing/Landing";
import LandingAccountRedirect from "@/components/landing/LandingAccountRedirect";
import PublicShell from "@/components/layout/PublicShell";
import { paths } from "@/lib/navigation";
import StoreProvider from "./StoreProviders";

function firstParam(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function Page({ searchParams }: PageProps<"/">) {
  const params = await searchParams;
  const reset = firstParam(params.reset_password);
  const experience = firstParam(params.experience);
  const slate = firstParam(params.slate);

  if (reset) redirect(`${paths.reset}?token=${encodeURIComponent(reset)}`);
  if (experience) redirect(`/experiences/${encodeURIComponent(experience)}`);
  if (slate) redirect(`${paths.results}?slate=${encodeURIComponent(slate)}`);
  if (params.verify_email !== undefined) redirect(paths.login);

  const landing = (
    <PublicShell>
      <main id="main" className="page-shell">
        <Landing />
      </main>
    </PublicShell>
  );

  const cookieStore = await cookies();
  if (!cookieStore.has("__Host-funilo_session") && !cookieStore.has("funilo_session_dev")) {
    return landing;
  }

  return (
    <StoreProvider allowUnavailable>
      <LandingAccountRedirect>{landing}</LandingAccountRedirect>
    </StoreProvider>
  );
}
