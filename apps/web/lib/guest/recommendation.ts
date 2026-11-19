import type { Context } from "@/types";
import { guestActivities, type GuestActivity } from "./catalog";

const intentDimensions: Record<Exclude<Context["activity_intent"], "any">, GuestActivity["dimension"]> = {
  unwind: "relaxation",
  switch_off: "detachment",
  learn: "mastery",
  connect: "affiliation",
  meaning: "meaning",
  choose: "autonomy",
};

const energyLevels = { low: 0, medium: 1, high: 2 };
const venues: Record<Context["venue"], readonly GuestActivity["venue"][]> = {
  home: ["home"],
  away_from_home: ["outdoor", "indoor_public"],
  any: ["home", "outdoor", "indoor_public"],
  outdoor: ["outdoor"],
  indoor_public: ["indoor_public"],
};

function cityKey(value: string) {
  return value.normalize("NFC").replace(/ك/g, "ک").replace(/[يى]/g, "ی")
    .replace(/[\s\u200c]/g, "").toLowerCase();
}

function fitsParty(activity: GuestActivity, context: Context) {
  const [min, max] = activity.people;
  if (context.social_mode !== "together" && min === 1) return true;
  return context.social_mode !== "solo"
    && context.party_size >= Math.max(2, min) && context.party_size <= max;
}

function energyFit(required: GuestActivity["energy"], available: Context["energy"]) {
  if (available === "unknown") return 0.5;
  const difference = energyLevels[required] - energyLevels[available];
  if (difference === 0) return 1;
  if (difference < 0) return 0.8;
  return difference === 1 ? 0.2 : 0;
}

export function recommendGuestActivity(context: Context): GuestActivity | undefined {
  const minutes = context.available_minutes;
  if (context.outing_days || !Number.isInteger(minutes) || minutes < 5 || minutes > 480) return;

  const requestedCity = context.allow_venue_planning && context.city ? cityKey(context.city) : "";
  const owns = new Set(context.owned_items);
  const likes = new Set(context.liked_tags);
  const intent = context.activity_intent === "any" ? null : intentDimensions[context.activity_intent];
  const suitableOutdoors = context.weather === "fair" && context.daylight === "day";
  let best: GuestActivity | undefined;
  let bestScore = -Infinity;

  for (const activity of guestActivities) {
    if (activity.minutes > minutes || !venues[context.venue].includes(activity.venue)) continue;
    if (!fitsParty(activity, context) || activity.items?.some((item) => !owns.has(item))) continue;
    if (activity.venue === "outdoor" && !suitableOutdoors) continue;
    // This snapshot has no verified prices for named places.
    if (activity.city && (context.budget.mode !== "flexible" || requestedCity !== cityKey(activity.city))) continue;

    const intentFit = intent ? Number(activity.dimension === intent) : 0.5;
    const interestFit = likes.size
      ? (activity.interests?.filter((tag) => likes.has(tag)).length ?? 0) / likes.size
      : 0.5;
    const timeFit = Math.min(1, activity.minutes / (minutes * 0.85));
    const score = 0.29 * intentFit + 0.33 * energyFit(activity.energy, context.energy)
      + 0.22 * interestFit + 0.16 * timeFit + (activity.city ? 0.14 : 0);
    if (score > bestScore) {
      best = activity;
      bestScore = score;
    }
  }

  return best;
}
