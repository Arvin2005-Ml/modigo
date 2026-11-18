import { createApi } from "@reduxjs/toolkit/query/react";
import { baseQuery } from "./baseQuery";

import type {
  User,
  Preferences,
  Saved,
  Context,
  Slate,
  Revision,
  Experience,
  Journey,
  LoginRequest,
  LoginResponse,
  SignupRequest,
  ResetPasswordRequest,
  CreateCheckInResponse,
  CreateSessionRequest,
  ReplaceSuggestionRequest,
  ReplaceSuggestionResponse,
  NavigateSessionRequest,
  StartExperienceRequest,
  CompleteExperienceResponse,
  FeedbackRequest,
  ItemsResponse,
  AdminActivity,
  AdminDraft,
  AdminJob,
  AdminListing,
  AdminListingParams,
  UpdateRevisionRequest,
  VersionedRevisionRequest,
  CookActivityRequest,
  WithdrawActivityRequest,
  CreateRevisionRequest,
  DiscoverItem,
} from "@/types";

export const apiSlice = createApi({
  reducerPath: "api",

  baseQuery,

  tagTypes: [
    "Me",
    "Saved",
    "Preferences",
    "Journey",
    "Experiences",
    "Session",
    "AdminActivities",
    "AdminActivity",
    "AdminJob",
  ],

  endpoints: (builder) => ({
    // -----------------------------
    // Authentication
    // -----------------------------

    getMe: builder.query<User, void>({
      query: () => ({
        url: "/me",
      }),
      providesTags: ["Me"],
    }),

    login: builder.mutation<LoginResponse, LoginRequest>({
      query: (body) => ({
        url: "/auth/login",
        method: "POST",
        body,
      }),
    }),

    signup: builder.mutation<unknown, SignupRequest>({
      query: (body) => ({
        url: "/auth/signup",
        method: "POST",
        body,
      }),
    }),

    forgotPassword: builder.mutation<unknown, { email: string }>({
      query: (body) => ({
        url: "/auth/forgot-password",
        method: "POST",
        body,
      }),
    }),

    resetPassword: builder.mutation<unknown, ResetPasswordRequest>({
      query: (body) => ({
        url: "/auth/reset-password",
        method: "POST",
        body,
      }),
    }),

    logout: builder.mutation<unknown, void>({
      query: () => ({
        url: "/auth/logout",
        method: "POST",
        body: {},
      }),
    }),

    // -----------------------------
    // Preferences
    // -----------------------------

    getPreferences: builder.query<Preferences, void>({
      query: () => ({
        url: "/me/preferences",
      }),
      providesTags: ["Preferences"],
    }),

    updatePreferences: builder.mutation<Preferences, Preferences>({
      query: (body) => ({
        url: "/me/preferences",
        method: "PUT",
        body,
      }),
      invalidatesTags: ["Preferences"],
    }),

    // -----------------------------
    // Saved Activities
    // -----------------------------
    getDiscover: builder.query<ItemsResponse<DiscoverItem>, void>({
      query: () => ({ url: "/discover" }),
    }),
    getSaved: builder.query<ItemsResponse<Saved>, void>({
      query: () => ({
        url: "/saved",
      }),
      providesTags: ["Saved"],
    }),

    saveActivity: builder.mutation<unknown, string>({
      query: (id) => ({
        url: `/saved/${id}`,
        method: "PUT",
        body: {},
      }),
      invalidatesTags: ["Saved"],
    }),

    removeSaved: builder.mutation<unknown, string>({
      query: (id) => ({
        url: `/saved/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Saved"],
    }),

    // -----------------------------
    // Recommendations
    // -----------------------------

    createCheckIn: builder.mutation<CreateCheckInResponse, Context>({
      query: (body) => ({
        url: "/check-ins",
        method: "POST",
        body,
      }),
    }),

    createSession: builder.mutation<Slate, CreateSessionRequest>({
      query: (body) => ({
        url: "/recommendation-sessions",
        method: "POST",
        body,
      }),
    }),

    getSession: builder.query<Slate, string>({
      query: (id) => ({
        url: `/recommendation-sessions/${id}`,
      }),
      providesTags: (_result, _error, id) => [
        {
          type: "Session",
          id,
        },
      ],
    }),

    getRevision: builder.query<Revision, string>({
      query: (id) => ({
        url: `/activity-revisions/${id}`,
      }),
    }),

    replaceSuggestion: builder.mutation<
      ReplaceSuggestionResponse,
      ReplaceSuggestionRequest
    >({
      query: ({ sessionId, slotId, expected_version }) => ({
        url:
          `/recommendation-sessions/${sessionId}` + `/slots/${slotId}/replace`,
        method: "POST",
        body: {
          expected_version,
        },
      }),

      invalidatesTags: (_result, _error, arg) => [
        {
          type: "Session",
          id: arg.sessionId,
        },
      ],
    }),

    navigateSession: builder.mutation<Slate, NavigateSessionRequest>({
      query: ({ sessionId, direction, expected_version }) => ({
        url: `/recommendation-sessions/${sessionId}` + `/navigate`,
        method: "POST",
        body: {
          direction,
          expected_version,
        },
      }),

      invalidatesTags: (_result, _error, arg) => [
        {
          type: "Session",
          id: arg.sessionId,
        },
      ],
    }),

    // -----------------------------
    // Experiences
    // -----------------------------

    getActiveExperience: builder.query<{ experience: Experience | null }, void>(
      {
        query: () => ({
          url: "/experiences/active",
        }),
        providesTags: ["Experiences"],
      },
    ),

    startExperience: builder.mutation<Experience, StartExperienceRequest>({
      query: (body) => ({
        url: "/experiences",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Experiences"],
    }),

    completeExperience: builder.mutation<CompleteExperienceResponse, string>({
      query: (id) => ({
        url: `/experiences/${id}/complete`,
        method: "POST",
        body: {},
      }),
      invalidatesTags: ["Experiences", "Journey"],
    }),

    cancelExperience: builder.mutation<unknown, string>({
      query: (id) => ({
        url: `/experiences/${id}/cancel`,
        method: "POST",
        body: {},
      }),
      invalidatesTags: ["Experiences"],
    }),

    sendFeedback: builder.mutation<unknown, FeedbackRequest>({
      query: ({ experienceId, rating, reason }) => ({
        url: `/experiences/${experienceId}/feedback`,
        method: "PUT",
        body: {
          rating,
          reason,
        },
      }),
    }),

    // -----------------------------
    // Journey
    // -----------------------------

    getJourney: builder.query<Journey, void>({
      query: () => ({
        url: "/me/journey",
      }),
      providesTags: ["Journey"],
    }),

    getExperienceHistory: builder.query<ItemsResponse<Experience>, void>({
      query: () => ({
        url: "/experiences?limit=100",
      }),
      providesTags: ["Experiences"],
    }),

    // -----------------------------
    // Admin: Activities
    // -----------------------------

    getAdminActivities: builder.query<AdminListing, AdminListingParams>({
      query: ({ limit, offset, state }) => ({
        url:
          `/admin/activities?limit=${limit}` +
          `&offset=${offset}` +
          (state ? `&state=${encodeURIComponent(state)}` : ""),
      }),
      providesTags: ["AdminActivities"],
    }),

    getAdminActivity: builder.query<AdminActivity, string>({
      query: (id) => ({
        url: `/admin/activities/${id}`,
      }),
      providesTags: ["AdminActivity"],
    }),

    // -----------------------------
    // Admin: Jobs
    // -----------------------------

    getAdminJob: builder.query<AdminJob, string>({
      query: (id) => ({
        url: `/admin/jobs/${id}`,
      }),
      providesTags: ["AdminJob"],
    }),

    cookAdminActivity: builder.mutation<AdminJob, CookActivityRequest>({
      query: ({ id, ...body }) => ({
        url: `/admin/activities/${id}/cook`,
        method: "POST",
        body,
      }),
      invalidatesTags: ["AdminJob"],
    }),

    cancelAdminJob: builder.mutation<AdminJob, string>({
      query: (id) => ({
        url: `/admin/jobs/${id}/cancel`,
        method: "POST",
        body: {},
      }),
      invalidatesTags: ["AdminJob"],
    }),

    // -----------------------------
    // Admin: Revisions
    // -----------------------------

    updateAdminRevision: builder.mutation<AdminDraft, UpdateRevisionRequest>({
      query: ({ id, ...body }) => ({
        url: `/admin/revisions/${id}`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: ["AdminActivity"],
    }),

    submitAdminRevision: builder.mutation<unknown, VersionedRevisionRequest>({
      query: ({ id, expected_draft_version }) => ({
        url: `/admin/revisions/${id}/submit`,
        method: "POST",
        body: {
          expected_draft_version,
        },
      }),
      invalidatesTags: ["AdminActivity", "AdminActivities"],
    }),

    publishAdminRevision: builder.mutation<unknown, VersionedRevisionRequest>({
      query: ({ id, expected_draft_version }) => ({
        url: `/admin/revisions/${id}/publish`,
        method: "POST",
        body: {
          expected_draft_version,
        },
      }),
      invalidatesTags: ["AdminActivity", "AdminActivities"],
    }),

    createAdminRevision: builder.mutation<unknown, CreateRevisionRequest>({
      query: ({ id, source_revision_id }) => ({
        url: `/admin/activities/${id}/revisions`,
        method: "POST",
        body: {
          source_revision_id,
        },
      }),
      invalidatesTags: ["AdminActivity"],
    }),

    withdrawAdminActivity: builder.mutation<unknown, WithdrawActivityRequest>({
      query: ({ id, reason }) => ({
        url: `/admin/activities/${id}/withdraw`,
        method: "POST",
        body: {
          reason,
        },
      }),
      invalidatesTags: ["AdminActivity", "AdminActivities"],
    }),

    reactivateAdminActivity: builder.mutation<unknown, WithdrawActivityRequest>(
      {
        query: ({ id, reason }) => ({
          url: `/admin/activities/${id}/reactivate`,
          method: "POST",
          body: {
            reason,
          },
        }),
        invalidatesTags: ["AdminActivity", "AdminActivities"],
      },
    ),
  }),
});

export const {
  useGetSavedQuery,
  useGetPreferencesQuery,
  useGetAdminActivitiesQuery,
} = apiSlice;
