export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number, public fields: Record<string, string> = {}) { super(message); }
}
let csrfToken: string | null = null;
let csrfRequest: Promise<void> | null = null;
const pending = new Map<string, string>();
const unavailable = 'ارتباط با سرور برقرار نشد؛ کمی بعد دوباره امتحان کن.';

async function readJson(response: Response) {
  if (response.status === 204) return undefined;
  try {
    return await response.json();
  } catch {
    // Proxies can return plain text or HTML, including for connection failures.
    throw new ApiError('NETWORK', unavailable, response.status);
  }
}

export async function refreshCsrf() {
  if (!csrfRequest) csrfRequest = (async () => {
    let response: Response;
    try {
      response = await fetch('/api/v1/auth/csrf', {credentials: 'include', cache: 'no-store'});
    } catch {
      throw new ApiError('NETWORK', unavailable, 0);
    }
    if (!response.ok) throw new ApiError('NETWORK', unavailable, response.status);
    const data = await readJson(response);
    if (!data || typeof data.csrf_token !== 'string') throw new ApiError('NETWORK', unavailable, response.status);
    csrfToken = data.csrf_token;
  })().finally(() => { csrfRequest = null; });
  await csrfRequest;
}

export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const mutation = method !== 'GET';
  if (mutation && !csrfToken) await refreshCsrf();
  const payload = body === undefined ? undefined : JSON.stringify(body);
  const scope = `${method}:${path}:${payload ?? ''}`;
  const headers: Record<string, string> = {};
  if (payload !== undefined) headers['Content-Type'] = 'application/json';
  if (mutation) headers['X-CSRF-Token'] = csrfToken!;
  if (method === 'POST' && !path.startsWith('/auth/')) {
    if (!pending.has(scope)) pending.set(scope, crypto.randomUUID());
    headers['Idempotency-Key'] = pending.get(scope)!;
  }
  const send = async () => {
    try {
      return await fetch('/api/v1' + path, {method, body: payload, headers, credentials: 'include', cache: 'no-store'});
    } catch { throw new ApiError('NETWORK', 'ارتباط قطع شد؛با همین دکمه دوباره امتحان کن.', 0); }
  };
  let response = await send();
  let data = await readJson(response);
  if (mutation && response.status === 403 && data?.error?.code === 'CSRF_FAILED') {
    // The API rejects CSRF before executing the mutation. Refresh once, keeping
    // the same payload and idempotency key after an expired pre-auth token.
    csrfToken = null;
    await refreshCsrf();
    headers['X-CSRF-Token'] = csrfToken!;
    response = await send();
    data = await readJson(response);
  }
  if (!response.ok) {
    if (response.status < 500 && response.status !== 429) pending.delete(scope);
    if (data?.error?.code === 'CSRF_FAILED') csrfToken = null;
    throw new ApiError(data?.error?.code || 'NETWORK', data?.error?.message || 'یه مشکلی پیش اومد؛دوباره امتحان کن.', response.status, data?.error?.fields);
  }
  pending.delete(scope);
  if (data?.csrf_token) csrfToken = data.csrf_token;
  if (path === '/auth/logout') csrfToken = null;
  return data as T;
}

export function digits(value: string) {
  return value.replace(/[۰-۹٠-٩]/g, c => String(c.charCodeAt(0) - (c >= '۰' ? 1776 : 1632)));
}
export const number = (n: number) => new Intl.NumberFormat('fa-IR').format(n);
export const badgeNames: Record<string, string> = {first_step: 'اولین قدم', five_moments: 'پنج لحظه برای خودت', ten_moments: 'ده لحظهٔ دوست‌داشتنی', curious_three: 'سه جور تجربه', all_six: 'شش پنجرهٔ تازه'};
