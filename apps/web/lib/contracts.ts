export type User = {id: string; display_name: string; email: string; role: 'user' | 'editor' | 'admin'; timezone: string};
export type Budget = {mode: 'free' | 'cap' | 'flexible'; cap_toman: number | null};
export type Context = {
  available_minutes: number; energy: 'low' | 'medium' | 'high' | 'unknown'; social_mode: 'solo' | 'together' | 'either';
  party_size: number; venue: 'home' | 'outdoor' | 'indoor_public' | 'any'; budget: Budget;
  mood: 'tired' | 'restless' | 'bored' | 'low' | 'okay' | 'skip';
  owned_items?: string[];
  liked_tags?: string[];
  goal?: 'unwind' | 'switch_off' | 'learn' | 'connect' | 'meaning' | 'choose' | 'any';
  need_now?: NonNullable<Context['goal']>;
  desired_outcome?: NonNullable<Context['goal']>;
  weather?: 'fair' | 'adverse' | 'unknown';
  daylight?: 'day' | 'night' | 'unknown';
};
export type Slot = {slot_id: string; activity_id?: string; revision_id?: string; title?: string; teaser?: string;
  total_minutes?: number; cost_label?: string; explanation?: string; unavailable: boolean};
export type ReplacementState = {replacement_count: number; replacement_limit: number; replacements_remaining: number; replacement_available: boolean;
  suggestion_index: number; suggestion_count: number};
export type Slate = ReplacementState & {id: string; check_in_id: string; version: number; items: Slot[]; result_count: number; partial: boolean; context_summary: Pick<Context, 'available_minutes'|'social_mode'|'party_size'|'venue'|'budget'>};
export type Content = {
  title: string; teaser: string; first_step: string; steps: string[]; lighter_version: string;
  materials_note: string; accessibility_note: string; conditions_note: string;
  active_minutes: number; setup_minutes: number; travel_minutes: number;
  safety_notes: string[]; primary_dimension: string; cost: {kind: string; note: string};
  [key: string]: unknown;
};
export type Revision = {id: string; activity_id: string; content: Content; origin: string};
export type Experience = {id: string; activity_id: string; revision_id: string; content_snapshot?: Content;
  status: 'active' | 'completed' | 'cancelled' | 'expired'; started_at: string; unavailable: boolean};
export type Award = {points: number; total_points: number; new_badges: string[]; reason: string};
export type Journey = {total_points: number; rewarded_completions: number; completed_dimensions: string[]; badges: string[]};
export type Saved = {activity_id: string; revision_id?: string; content?: Content; unavailable: boolean};
export type Preferences = {version: number; preferences: {
  liked_tags: string[]; blocked_tags: string[]; owned_items: string[]; max_mobility: 'seated' | 'light' | 'active';
  requires_step_free: boolean; requires_quiet: boolean; allow_async_contact: boolean;
  default_goal: NonNullable<Context['goal']>; show_gamification: boolean; analytics_opt_in: false; analytics_policy_version: null;
}};
