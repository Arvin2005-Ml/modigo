import type { Content } from "./domain";

export type AdminDraft = {
  id: string;
  revision_number: number;
  draft_version: number;
  state: string;
  content: Content | null;
  origin: string;
};

export type AdminActivity = {
  id: string;
  raw_title: string;
  seed_key: string;
  primary_dimension: string;
  active: boolean;
  withdrawn?: boolean;
  revisions?: AdminDraft[];
};

export type AdminJob = {
  id: string;
  activity_id: string;
  state: string;
  provider: string;
  error_code: string | null;
};

export type AdminListing = {
  items: AdminActivity[];
  total: number;
  next_offset: number | null;
};

export type AdminListingParams = {
  limit: number;
  offset: number;
  state: string;
};
