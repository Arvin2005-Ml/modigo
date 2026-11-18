import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

import type { User } from "@/types";

export type AuthStatus = "checking" | "authenticated" | "guest" | "unavailable";

type AuthState = {
  user: User | null;
  status: AuthStatus;
};

const initialState: AuthState = {
  user: null,
  status: "checking",
};

const authSlice = createSlice({
  name: "auth",
  initialState,

  reducers: {
    setAuthChecking: (state) => {
      state.user = null;
      state.status = "checking";
    },

    setUser: (state, action: PayloadAction<User>) => {
      state.user = action.payload;
      state.status = "authenticated";
    },

    clearUser: (state) => {
      state.user = null;
      state.status = "guest";
    },

    setAuthUnavailable: (state) => {
      state.user = null;
      state.status = "unavailable";
    },
  },
});

export const { setAuthChecking, setUser, clearUser, setAuthUnavailable } =
  authSlice.actions;

export default authSlice.reducer;
