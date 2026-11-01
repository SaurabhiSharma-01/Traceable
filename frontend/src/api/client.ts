/**
 * client.ts — Lightweight typed fetch wrapper for the Traceable backend API.
 */

export interface ApiErrorPayload {
  status: number;
  error: string;
  message: string;
}

export class ApiError extends Error {
  status: number;
  error: string;

  constructor(payload: ApiErrorPayload) {
    super(payload.message || 'An unexpected API error occurred');
    this.name = 'ApiError';
    this.status = payload.status;
    this.error = payload.error;
  }
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {},
  timeoutMs: number = 60000,
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const mergedSignal = options.signal
    ? options.signal
    : controller.signal;

  try {
    const url = endpoint.startsWith('http') ? endpoint : `${BASE_URL}${endpoint}`;
    const res = await fetch(url, {
      ...options,
      signal: mergedSignal,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    });

    if (!res.ok) {
      let errorData: any = {};
      try {
        errorData = await res.json();
      } catch {
        errorData = { message: res.statusText };
      }

      throw new ApiError({
        status: res.status,
        error: errorData.error || (res.status === 422 ? 'validation_error' : 'request_failed'),
        message:
          errorData.message ||
          errorData.detail ||
          (typeof errorData === 'string' ? errorData : `Request failed with status ${res.status}`),
      });
    }

    return (await res.json()) as T;
  } catch (err: any) {
    if (err.name === 'AbortError') {
      throw new ApiError({
        status: 408,
        error: 'timeout',
        message: 'The request timed out. Please check your network connection and try again.',
      });
    }
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError({
      status: 0,
      error: 'network_error',
      message: err.message || 'Unable to connect to the Traceable server.',
    });
  } finally {
    clearTimeout(timeoutId);
  }
}

