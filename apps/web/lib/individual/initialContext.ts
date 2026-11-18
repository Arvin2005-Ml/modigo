import type { Context } from "@/types";

export const initialContext: Context = {
  available_minutes: 30,
  energy: "low",
  social_mode: "solo",
  party_size: 1,
  venue: "home",
  budget: {
    mode: "free",
    cap_toman: null,
  },
  activity_intent: "any",
};
