"use client";

import { useEffect, useState, type ReactNode } from "react";

import { apiSlice } from "@/lib/store/api/apiSlice";
import { toApiError } from "@/lib/store/api/baseQuery";
import { useAppDispatch, useAppSelector } from "@/lib/store/hooks";

import {
  clearUser,
  setAuthChecking,
  setAuthUnavailable,
  setUser,
} from "@/lib/store/slices/authSlice";

import { Button } from "@/components/ui";

type Props = {
  children: ReactNode;
  allowUnavailable?: boolean;
};

export default function AuthBootstrap({ children, allowUnavailable = false }: Props) {
  const dispatch = useAppDispatch();

  const status = useAppSelector((state) => state.auth.status);

  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;

    const request = dispatch(
      apiSlice.endpoints.getMe.initiate(undefined, {
        subscribe: false,
        forceRefetch: true,
      }),
    );

    void request
      .unwrap()
      .then((user) => {
        if (active) {
          dispatch(setUser(user));
        }
      })
      .catch((error: unknown) => {
        if (!active) return;

        const apiError = toApiError(error);

        if (apiError.status === 401) {
          dispatch(clearUser());
        } else {
          dispatch(setAuthUnavailable());
        }
      });

    return () => {
      active = false;
      request.unsubscribe();
    };
  }, [dispatch, attempt]);

  const retry = () => {
    dispatch(setAuthChecking());
    setAttempt((current) => current + 1);
  };

  if (status === "checking") {
    return (
      <main id="main" className="route-loading" role="status">
        در حال بررسی حساب مودیگو…
      </main>
    );
  }

  if (status === "unavailable" && !allowUnavailable) {
    return (
      <main id="main" className="route-loading">
        <h1>فعلاً به سرور دسترسی نداریم.</h1>

        <p>
          اتصال اینترنت یا وضعیت سرور را بررسی کن. اطلاعات حساب تو حذف نشده‌اند.
        </p>

        <Button onClick={retry}>تلاش دوباره</Button>
      </main>
    );
  }

  return <>{children}</>;
}
