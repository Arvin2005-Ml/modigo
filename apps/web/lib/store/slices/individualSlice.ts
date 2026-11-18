import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

import type { Context } from "@/types";

import { initialContext } from "@/lib/individual/initialContext";
import { clearUser, setUser } from "./authSlice";

type IndividualState = {
  context: Context;
};

function makeInitialState(): IndividualState {
  return {
    context: {
      ...initialContext,
      budget: {
        ...initialContext.budget,
      },
    },
  };
}

const individualSlice = createSlice({
  name: "individual",
  initialState: makeInitialState(),

  reducers: {
    setIndividualContext: (state, action: PayloadAction<Context>) => {
      state.context = action.payload;
    },

    resetIndividualContext: () => makeInitialState(),
  },

  extraReducers: (builder) => {
    // A new login must not inherit another user's draft.
    builder.addCase(setUser, () => makeInitialState());

    // Clear private drafts on logout/session expiry.
    builder.addCase(clearUser, () => makeInitialState());
  },
});

export const { setIndividualContext, resetIndividualContext } =
  individualSlice.actions;

export default individualSlice.reducer;
