"use client";

import { useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";

import { ApiError } from "@/lib/api";
import { paths, safeNextPath } from "@/lib/navigation";

import { useAppDispatch, useAppSelector } from "@/lib/store/hooks";
import { apiSlice } from "@/lib/store/api/apiSlice";
import { createApiClient } from "@/lib/store/api/apiClient";

import { clearUser, setUser } from "@/lib/store/slices/authSlice";

export function useAuth() {
  const dispatch = useAppDispatch();
  const router = useRouter();

  const { user, status } = useAppSelector((state) => state.auth);

  const client = useMemo(() => createApiClient(dispatch), [dispatch]);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await client.login({
        email,
        password,
      });

      // Remove data from any previous account.
      dispatch(apiSlice.util.resetApiState());
      dispatch(setUser(response.user));

      return response.user;
    },
    [client, dispatch],
  );

  const signup = useCallback(
    async (email: string, password: string, name: string) => {
      await client.signup({
        email,
        password,
        display_name: name,
        adult_confirmed: true,
      });

      // Preserve the current auto-login behavior.
      return login(email, password);
    },
    [client, login],
  );

  const forgotPassword = useCallback(
    async (email: string) => {
      await client.forgotPassword(email);
    },
    [client],
  );

  const resetPassword = useCallback(
    async (token: string, password: string) => {
      await client.resetPassword({
        token,
        new_password: password,
      });

      dispatch(clearUser());
      dispatch(apiSlice.util.resetApiState());

      router.replace(`${paths.login}?reset=success`);
    },
    [client, dispatch, router],
  );

  const logout = useCallback(async () => {
    try {
      await client.logout();
    } catch (error) {
      // If the session is already expired, local cleanup
      // is still appropriate.
      if (!(error instanceof ApiError) || error.status !== 401) {
        throw error;
      }
    }

    dispatch(clearUser());
    dispatch(apiSlice.util.resetApiState());

    // Full navigation clears legacy Funilo state.
    window.location.replace(paths.landing);
  }, [client, dispatch]);

  const expireSession = useCallback(
    (returnTo: string = paths.discover) => {
      dispatch(clearUser());
      dispatch(apiSlice.util.resetApiState());

      const next = safeNextPath(returnTo) ?? paths.discover;

      router.replace(`${paths.login}?next=${encodeURIComponent(next)}`);
    },
    [dispatch, router],
  );

  return {
    user,
    status,

    login,
    signup,
    forgotPassword,
    resetPassword,
    logout,
    expireSession,
  };
}
