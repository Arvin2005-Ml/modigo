"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/hooks/useAuth";
import { paths } from "@/lib/navigation";
import { useAppDispatch } from "@/lib/store/hooks";
import { apiSlice } from "@/lib/store/api/apiSlice";
import { toApiError } from "@/lib/store/api/baseQuery";
import { isUnauthorized, usePrivatePageAuth } from "@/lib/usePrivatePageAuth";

import type { Preferences as PreferencesType } from "@/types";

import Preferences from "@/components/Preferences";
import { Button } from "@/components/ui";

export default function SettingsPage() {
  const dispatch = useAppDispatch();

  const { user, redirecting, authError, retryAuth, expireSession } =
    usePrivatePageAuth(paths.settings);

  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const { logout: logoutSession } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const preferencesQuery = apiSlice.endpoints.getPreferences.useQuery(
    undefined,
    {
      skip: !user || redirecting,
    },
  );

  const [updatePreferences, { isLoading: isSaving }] =
    apiSlice.endpoints.updatePreferences.useMutation();

  const busy = isSaving || isLoggingOut;

  useEffect(() => {
    if (isUnauthorized(preferencesQuery.error)) {
      expireSession();
    }
  }, [preferencesQuery.error, expireSession]);

  const handleSave = async (values: PreferencesType): Promise<void> => {
    if (busy) return;

    setNotice("");
    setActionError("");

    try {
      await updatePreferences(values).unwrap();

      // updatePreferences invalidates the Preferences tag.
      // The query will receive the updated version.
      setNotice("انتخاب‌هات نگه داشته شد.");
    } catch (error) {
      const apiError = toApiError(error);

      if (apiError.status === 401) {
        expireSession();
        return;
      }

      setActionError(apiError.message);
    }
  };

  const handleLogout = async (): Promise<void> => {
    if (busy) return;

    setIsLoggingOut(true);
    setNotice("");
    setActionError("");

    try {
      await logoutSession();
    } catch (error) {
      const apiError = toApiError(error);

      setActionError(apiError.message);
      setIsLoggingOut(false);
    }
  };

  if (!user || redirecting) {
    return (
      <main id="main" className="page-shell">
        {authError ? (
          <div className="error-banner" role="alert">
            <p>
              بررسی حساب انجام نشد. اتصال سرور را بررسی کن و دوباره تلاش کن.
            </p>

            <Button secondary onClick={retryAuth}>
              تلاش دوباره
            </Button>
          </div>
        ) : (
          <div className="loading-state" role="status">
            <p>در حال بررسی حساب…</p>
          </div>
        )}
      </main>
    );
  }

  const preferences = preferencesQuery.data;

  return (
    <main id="main" className="page-shell" aria-busy={busy}>
      {actionError && (
        <div className="error-banner" role="alert">
          <p>{actionError}</p>

          <button
            type="button"
            className="text-button"
            onClick={() => setActionError("")}
            aria-label="بستن پیام خطا"
          >
            بستن
          </button>
        </div>
      )}

      <div className="status-region" role="status" aria-live="polite">
        {notice && <p className="notice-message">{notice}</p>}
      </div>

      {preferencesQuery.isLoading || preferencesQuery.isUninitialized ? (
        <div className="loading-state" role="status">
          <p>در حال دریافت تنظیمات…</p>
        </div>
      ) : preferencesQuery.isError ? (
        <section className="detail-column">
          <h1>تنظیمات من</h1>

          <div className="error-banner" role="alert">
            <p>دریافت تنظیمات انجام نشد.</p>

            <Button secondary onClick={() => void preferencesQuery.refetch()}>
              تلاش دوباره
            </Button>
          </div>
        </section>
      ) : preferences ? (
        <Preferences
          key={preferences.version}
          initial={preferences}
          busy={busy}
          save={handleSave}
        />
      ) : null}

      <div className="account-footer">
        <p className="hint">{user.email}</p>

        <button
          type="button"
          className="text-button"
          disabled={busy}
          onClick={() => void handleLogout()}
        >
          {isLoggingOut ? "در حال خروج…" : "خروج از حساب"}
        </button>
      </div>
    </main>
  );
}
