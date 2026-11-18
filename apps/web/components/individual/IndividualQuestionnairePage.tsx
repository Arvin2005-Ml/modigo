"use client";

import { useEffect, useRef, useState } from "react";

import { useRouter } from "next/navigation";

import { paths } from "@/lib/navigation";
import { useAuth } from "@/lib/hooks/useAuth";
import { useAppDispatch, useAppSelector } from "@/lib/store/hooks";

import { apiSlice, useGetPreferencesQuery } from "@/lib/store/api/apiSlice";

import { toApiError } from "@/lib/store/api/baseQuery";
import { setIndividualContext } from "@/lib/store/slices/individualSlice";

import Questionnaire from "@/components/Questionnaire";
import { Button } from "@/components/ui";

type CheckInCache = {
  fingerprint: string;
  id: string;
};

export default function IndividualQuestionnairePage() {
  const router = useRouter();
  const dispatch = useAppDispatch();

  const { user, expireSession } = useAuth();

  const context = useAppSelector((state) => state.individual.context);

  const preferencesQuery = useGetPreferencesQuery(undefined, {
    skip: !user,
  });

  const [createCheckIn] = apiSlice.endpoints.createCheckIn.useMutation();

  const [createSession] = apiSlice.endpoints.createSession.useMutation();

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const checkIn = useRef<CheckInCache | null>(null);
  const locked = useRef(false);

  // A changed Preferences version invalidates the
  // cached CheckIn, even if answers stay the same.
  useEffect(() => {
    checkIn.current = null;
  }, [preferencesQuery.data?.version]);

  useEffect(() => {
    if (
      preferencesQuery.error &&
      "status" in preferencesQuery.error &&
      preferencesQuery.error.status === 401
    ) {
      expireSession(paths.questions);
    }
  }, [preferencesQuery.error, expireSession]);

  const handleChange = (next: typeof context) => {
    dispatch(setIndividualContext(next));
    checkIn.current = null;
    setError("");
  };

  const handleRecommend = async (): Promise<void> => {
    if (locked.current) return;

    locked.current = true;
    setBusy(true);
    setError("");

    try {
      const fingerprint = JSON.stringify(context);

      if (!checkIn.current || checkIn.current.fingerprint !== fingerprint) {
        const result = await createCheckIn(context).unwrap();

        checkIn.current = {
          fingerprint,
          id: result.id,
        };
      }

      const session = await createSession({
        check_in_id: checkIn.current.id,
      }).unwrap();

      router.push(`${paths.results}?slate=${encodeURIComponent(session.id)}`);
    } catch (error) {
      const apiError = toApiError(error);

      if (apiError.status === 401) {
        expireSession(paths.questions);
      } else {
        setError(apiError.message);
      }
    } finally {
      locked.current = false;
      setBusy(false);
    }
  };

  return (
    <main id="main" className="page-shell" aria-busy={busy}>
      {error && (
        <div className="error-banner" role="alert">
          <p>{error}</p>

          <button
            type="button"
            className="text-button"
            onClick={() => setError("")}
          >
            بستن
          </button>
        </div>
      )}

      {preferencesQuery.isError &&
        !(
          preferencesQuery.error &&
          "status" in preferencesQuery.error &&
          preferencesQuery.error.status === 401
        ) && (
          <div className="soft-note">
            <p>
              دریافت سلیقه‌های حساب انجام نشد. می‌تونی فرم رو ادامه بدی یا
              دوباره امتحان کنی.
            </p>

            <Button
              secondary
              disabled={busy}
              onClick={() => void preferencesQuery.refetch()}
            >
              دریافت دوبارهٔ سلیقه‌ها
            </Button>
          </div>
        )}

      <Questionnaire
        value={context}
        defaults={preferencesQuery.data?.preferences}
        change={handleChange}
        submit={() => {
          void handleRecommend();
        }}
        busy={busy}
      />
    </main>
  );
}
