/**
 * understand.ts — API client call for query understanding.
 */
import { UnderstandingResult } from '../types';
import { apiClient } from './client';

export async function understand(
  question: string,
  signal?: AbortSignal,
): Promise<UnderstandingResult> {
  return apiClient<UnderstandingResult>(
    '/api/understand',
    {
      method: 'POST',
      body: JSON.stringify({ question }),
      signal,
    },
    60000,
  );
}

