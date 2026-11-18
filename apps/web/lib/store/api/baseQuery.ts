import type {BaseQueryFn} from '@reduxjs/toolkit/query';

import {
  api,
  ApiError,
} from '@/lib/api';

import type {
  ApiFailure,
  ApiRequest,
} from '@/types';

export const baseQuery: BaseQueryFn<
  ApiRequest,
  unknown,
  ApiFailure
> = async ({
  url,
  method = 'GET',
  body,
}) => {
  try {
    const data = await api<unknown>(url, method, body);

    return {
      // RTK Query requires a defined success value, including for HTTP 204.
      data: data === undefined ? null : data,
    };
  } catch (error) {
    if (error instanceof ApiError) {
      return {
        error: {
          status: error.status,
          code: error.code,
          message: error.message,
          fields: error.fields,
        },
      };
    }

    return {
      error: {
        status: 0,
        code: 'NETWORK',
        message:
          'ارتباط با سرور برقرار نشد؛دوباره امتحان کن.',
        fields: {},
      },
    };
  }
};

function isStringFields(
  value: unknown
): value is Record<string, string> {
  return (
    typeof value === 'object' &&
    value !== null &&
    Object.entries(value).every(
      ([, item]) => typeof item === 'string'
    )
  );
}

export function toApiError(
  error: unknown
): ApiError {
  if (error instanceof ApiError) {
    return error;
  }

  if (
    typeof error === 'object' &&
    error !== null &&
    'status' in error &&
    'message' in error
  ) {
    const value = error as {
      status: unknown;
      message: unknown;
      code?: unknown;
      fields?: unknown;
    };

    return new ApiError(
      typeof value.code === 'string'
        ? value.code
        : 'NETWORK',

      typeof value.message === 'string'
        ? value.message
        : 'یه مشکلی پیش اومد؛دوباره امتحان کن.',

      typeof value.status === 'number'
        ? value.status
        : 0,

      isStringFields(value.fields)
        ? value.fields
        : {}
    );
  }

  return new ApiError(
    'UNKNOWN',
    error instanceof Error
      ? error.message
      : 'یه مشکلی پیش اومد؛دوباره امتحان کن.',
    0
  );
}
