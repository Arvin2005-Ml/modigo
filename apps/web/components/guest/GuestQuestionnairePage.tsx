"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import Questionnaire from "@/components/Questionnaire";
import { initialContext } from "@/lib/individual/initialContext";
import { guestSignupPath, paths } from "@/lib/navigation";
import { recommendGuestActivity } from "@/lib/guest/recommendation";
import { storeGuestSuggestion, useStoredGuestSuggestion } from "@/lib/guest/suggestionStorage";

export default function GuestQuestionnairePage() {
  const router = useRouter();
  const stored = useStoredGuestSuggestion();
  const used = typeof stored === "string";
  const [context, setContext] = useState(initialContext);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);

  useEffect(() => {
    if (used && !busy) router.replace(guestSignupPath);
  }, [busy, router, used]);

  const submit = async () => {
    if (submitting.current) return;
    const activity = recommendGuestActivity(context);
    if (!activity) {
      setMessage("با این شرایط پیشنهادی پیدا نکردیم. می‌تونی به قدم‌های قبلی برگردی و جواب‌هات رو تغییر بدی.");
      return;
    }

    submitting.current = true;
    setBusy(true);
    setMessage("");
    try {
      const claimed = await storeGuestSuggestion(activity.key);
      router.replace(claimed ? paths.guestResult : guestSignupPath);
    } catch {
      setMessage("ذخیرهٔ پیشنهاد در مرورگرت انجام نشد. دوباره امتحان کن.");
      submitting.current = false;
      setBusy(false);
    }
  };

  if (stored === false) {
    return (
      <main id="main" className="route-loading">
        <h1>مرورگرت اجازهٔ ذخیرهٔ پیشنهاد رو نمی‌ده.</h1>
        <Link className="button-primary" href={guestSignupPath}>ساخت حساب</Link>
      </main>
    );
  }

  if (stored === undefined || (used && !busy)) {
    return <main id="main" className="route-loading" role="status">در حال آماده‌سازی…</main>;
  }

  return (
    <main id="main" className="page-shell" aria-busy={busy}>
      <Questionnaire
        value={context}
        change={(next) => {
          setContext(next);
          setMessage("");
        }}
        submit={() => void submit()}
        busy={busy}
        submitMessage={message}
      />
    </main>
  );
}
