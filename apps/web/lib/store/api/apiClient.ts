import { apiSlice } from "./apiSlice";
import { toApiError } from "./baseQuery";

import type { AppDispatch } from "../store";

import type {
  Context,
  Preferences,
  LoginRequest,
  SignupRequest,
  ResetPasswordRequest,
  CreateSessionRequest,
  ReplaceSuggestionRequest,
  NavigateSessionRequest,
  StartExperienceRequest,
  FeedbackRequest,
  UpdateRevisionRequest,
  VersionedRevisionRequest,
  CookActivityRequest,
  CreateRevisionRequest,
  WithdrawActivityRequest,
} from "@/types";

export function createApiClient(dispatch: AppDispatch) {
  const run = <T>(promise: Promise<T>): Promise<T> =>
    promise.catch((error) => {
      throw toApiError(error);
    });

  const queryOptions = {
    subscribe: false,
    forceRefetch: true,
  } as const;

  return {
    getMe: () =>
      run(
        dispatch(
          apiSlice.endpoints.getMe.initiate(undefined, queryOptions),
        ).unwrap(),
      ),

    login: (body: LoginRequest) =>
      run(dispatch(apiSlice.endpoints.login.initiate(body)).unwrap()),

    signup: (body: SignupRequest) =>
      run(dispatch(apiSlice.endpoints.signup.initiate(body)).unwrap()),

    forgotPassword: (email: string) =>
      run(
        dispatch(
          apiSlice.endpoints.forgotPassword.initiate({
            email,
          }),
        ).unwrap(),
      ),

    resetPassword: (body: ResetPasswordRequest) =>
      run(dispatch(apiSlice.endpoints.resetPassword.initiate(body)).unwrap()),

    logout: () => run(dispatch(apiSlice.endpoints.logout.initiate()).unwrap()),

    updatePreferences: (body: Preferences) =>
      run(
        dispatch(apiSlice.endpoints.updatePreferences.initiate(body)).unwrap(),
      ),

    saveActivity: (id: string) =>
      run(dispatch(apiSlice.endpoints.saveActivity.initiate(id)).unwrap()),

    removeSaved: (id: string) =>
      run(dispatch(apiSlice.endpoints.removeSaved.initiate(id)).unwrap()),

    createCheckIn: (body: Context) =>
      run(dispatch(apiSlice.endpoints.createCheckIn.initiate(body)).unwrap()),

    createSession: (body: CreateSessionRequest) =>
      run(dispatch(apiSlice.endpoints.createSession.initiate(body)).unwrap()),

    getSession: (id: string) =>
      run(
        dispatch(
          apiSlice.endpoints.getSession.initiate(id, queryOptions),
        ).unwrap(),
      ),

    getRevision: (id: string) =>
      run(
        dispatch(
          apiSlice.endpoints.getRevision.initiate(id, queryOptions),
        ).unwrap(),
      ),

    replaceSuggestion: (body: ReplaceSuggestionRequest) =>
      run(
        dispatch(apiSlice.endpoints.replaceSuggestion.initiate(body)).unwrap(),
      ),

    navigateSession: (body: NavigateSessionRequest) =>
      run(dispatch(apiSlice.endpoints.navigateSession.initiate(body)).unwrap()),

    getActiveExperience: () =>
      run(
        dispatch(
          apiSlice.endpoints.getActiveExperience.initiate(
            undefined,
            queryOptions,
          ),
        ).unwrap(),
      ),

    startExperience: (body: StartExperienceRequest) =>
      run(dispatch(apiSlice.endpoints.startExperience.initiate(body)).unwrap()),

    completeExperience: (id: string) =>
      run(
        dispatch(apiSlice.endpoints.completeExperience.initiate(id)).unwrap(),
      ),

    cancelExperience: (id: string) =>
      run(dispatch(apiSlice.endpoints.cancelExperience.initiate(id)).unwrap()),

    sendFeedback: (body: FeedbackRequest) =>
      run(dispatch(apiSlice.endpoints.sendFeedback.initiate(body)).unwrap()),

    getJourney: () =>
      run(
        dispatch(
          apiSlice.endpoints.getJourney.initiate(undefined, queryOptions),
        ).unwrap(),
      ),

    getExperienceHistory: () =>
      run(
        dispatch(
          apiSlice.endpoints.getExperienceHistory.initiate(
            undefined,
            queryOptions,
          ),
        ).unwrap(),
      ),

    getAdminActivity: (id: string) =>
      run(
        dispatch(
          apiSlice.endpoints.getAdminActivity.initiate(id, queryOptions),
        ).unwrap(),
      ),

    getAdminJob: (id: string) =>
      run(
        dispatch(
          apiSlice.endpoints.getAdminJob.initiate(id, queryOptions),
        ).unwrap(),
      ),

    cookAdminActivity: (body: CookActivityRequest) =>
      run(
        dispatch(apiSlice.endpoints.cookAdminActivity.initiate(body)).unwrap(),
      ),

    cancelAdminJob: (id: string) =>
      run(dispatch(apiSlice.endpoints.cancelAdminJob.initiate(id)).unwrap()),

    updateAdminRevision: (body: UpdateRevisionRequest) =>
      run(
        dispatch(
          apiSlice.endpoints.updateAdminRevision.initiate(body),
        ).unwrap(),
      ),

    submitAdminRevision: (body: VersionedRevisionRequest) =>
      run(
        dispatch(
          apiSlice.endpoints.submitAdminRevision.initiate(body),
        ).unwrap(),
      ),

    publishAdminRevision: (body: VersionedRevisionRequest) =>
      run(
        dispatch(
          apiSlice.endpoints.publishAdminRevision.initiate(body),
        ).unwrap(),
      ),

    createAdminRevision: (body: CreateRevisionRequest) =>
      run(
        dispatch(
          apiSlice.endpoints.createAdminRevision.initiate(body),
        ).unwrap(),
      ),

    withdrawAdminActivity: (body: WithdrawActivityRequest) =>
      run(
        dispatch(
          apiSlice.endpoints.withdrawAdminActivity.initiate(body),
        ).unwrap(),
      ),

    reactivateAdminActivity: (body: WithdrawActivityRequest) =>
      run(
        dispatch(
          apiSlice.endpoints.reactivateAdminActivity.initiate(body),
        ).unwrap(),
      ),
  };
}
