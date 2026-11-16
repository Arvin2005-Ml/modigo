import type { Award, Experience, ReplacementState, Slot, User } from "./domain";

export type ApiRequest = {
  url: string;
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
};

export type ApiFailure = {
  status: number;
  code: string;
  message: string;
  fields: Record<string, string>;
};

export type ItemsResponse<T> = {
  items: T[];
};

export type LoginRequest = {
  email: string;
  password: string;
};

export type LoginResponse = {
  user: User;
};

export type SignupRequest = LoginRequest & {
  display_name: string;
  adult_confirmed: true;
};

export type ResetPasswordRequest = {
  token: string | null;
  new_password: string;
};

export type CreateCheckInResponse = {
  id: string;
};

export type CreateSessionRequest = {
  check_in_id: string;
};

export type ReplaceSuggestionRequest = {
  sessionId: string;
  slotId: string;
  expected_version: number;
};

export type ReplaceSuggestionResponse = ReplacementState & {
  session_version: number;
  item: Slot;
  replaced: boolean;
};

export type NavigateSessionRequest = {
  sessionId: string;
  direction: "previous" | "next";
  expected_version: number;
};

export type StartExperienceRequest = {
  recommendation_session_id: string;
  slot_id: string;
  revision_id?: string;
};

export type CompleteExperienceResponse = {
  experience: Experience;
  award: Award;
};

export type FeedbackRequest = {
  experienceId: string;
  rating: "liked" | "neutral" | "disliked";
  reason: null;
};

export type UpdateRevisionRequest = {
  id: string;
  expected_draft_version: number;
  content: unknown;
};

export type VersionedRevisionRequest = {
  id: string;
  expected_draft_version: number;
};

export type CookActivityRequest = {
  id: string;
  target_draft_id: string;
  expected_draft_version: number;
  prompt_version: "cook_v1";
  editor_constraints: string;
};

export type WithdrawActivityRequest = {
  id: string;
  reason: string;
};

export type CreateRevisionRequest = {
  id: string;
  source_revision_id: string;
};
