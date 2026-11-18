export type User = {
  id: string;
  display_name: string;
  email: string;
  role: "user" | "editor" | "admin";
  timezone: string;
};

export type Budget = {
  mode: "free" | "cap" | "flexible";
  cap_toman: number | null;
};

export type OutingDays = 1 | 2;
export type OutingOrigin = "تهران" | "مشهد" | "اصفهان" | "شیراز" | "تبریز";

export type Context = {
  available_minutes: number;
  outing_days?: OutingDays | null;
  energy: "low" | "medium" | "high" | "unknown";
  social_mode: "solo" | "together" | "either";
  party_size: number;
  venue: "home" | "away_from_home" | "outdoor" | "indoor_public" | "any";
  budget: Budget;
  activity_intent: NonNullable<Context["goal"]>;
  owned_items?: string[];
  liked_tags?: string[];
  goal?:
    | "unwind"
    | "switch_off"
    | "learn"
    | "connect"
    | "meaning"
    | "choose"
    | "any";
  allow_venue_planning?: boolean;
  city?: string | null;
  weather?: "fair" | "adverse" | "unknown";
  daylight?: "day" | "night" | "unknown";
};

export type Place = {
  name: string;
  city: string;
  source_url: string;
  source_name: string;
  program?: { url: string; label: string; scope: "venue" | "collection" | "directory" };
};

export type Slot = {
  slot_id: string;
  activity_id?: string;
  revision_id?: string;
  title?: string;
  teaser?: string;
  total_minutes?: number;
  cost_label?: string;
  cost_range_toman?: { min: number; max: number } | null;
  explanation?: string;
  place?: Place | null;
  venue_check_message?: string | null;
  unavailable: boolean;
};

export type ReplacementState = {
  replacement_count: number;
  replacement_limit: number;
  replacements_remaining: number;
  replacement_available: boolean;
  suggestion_index: number;
  suggestion_count: number;
};

export type Slate = ReplacementState & {
  id: string;
  check_in_id: string;
  version: number;
  items: Slot[];
  result_count: number;
  partial: boolean;
  venue_alternative?: { title: string; venue: "home" | "outdoor" | "indoor_public"; total_minutes: number } | null;
  budget_alternative?: { title: string; total_minutes: number } | null;
  context_summary: Pick<
    Context,
    "available_minutes" | "social_mode" | "party_size" | "venue" | "budget"
  > & Pick<Context, "city" | "allow_venue_planning" | "outing_days">;
};

export type Content = {
  title: string;
  teaser: string;
  first_step: string;
  steps: string[];
  lighter_version: string;
  materials_note: string;
  accessibility_note: string;
  conditions_note: string;
  active_minutes: number;
  setup_minutes: number;
  travel_minutes: number;
  safety_notes: string[];
  primary_dimension: string;
  cost: {
    kind: string;
    note: string;
  };
  place?: Place | null;
  requires_venue_check?: boolean;
  [key: string]: unknown;
};

export type Revision = {
  id: string;
  activity_id: string;
  content: Content;
  origin: string;
  catalog_start: {
    min_people: number;
    max_people: number;
    checks: ("venue" | "cost" | "materials" | "weather" | "daylight" | "contact")[];
  } | null;
};

export type Experience = {
  id: string;
  activity_id: string;
  revision_id: string;
  content_snapshot?: Content;
  status: "active" | "completed" | "cancelled" | "expired";
  started_at: string;
  unavailable: boolean;
};

export type Award = {
  points: number;
  total_points: number;
  new_badges: string[];
  reason: string;
};

export type Journey = {
  total_points: number;
  rewarded_completions: number;
  completed_dimensions: string[];
  badges: string[];
};

export type Saved = {
  activity_id: string;
  revision_id?: string;
  content?: Content;
  unavailable: boolean;
};

export type Preferences = {
  version: number;
  preferences: {
    liked_tags: string[];
    blocked_tags: string[];
    owned_items: string[];
    max_mobility: "seated" | "light" | "active";
    requires_step_free: boolean;
    requires_quiet: boolean;
    allow_async_contact: boolean;
    default_goal: NonNullable<Context["goal"]>;
    show_gamification: boolean;
    analytics_opt_in: false;
    analytics_policy_version: null;
  };
};
export type DiscoverItem = {
  activity_id: string;
  revision_id: string;
  title: string;
  primary_dimension: string;
};
