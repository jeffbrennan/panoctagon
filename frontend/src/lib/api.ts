const cache = new Map<string, { value: unknown; expires: number }>();
const MAX_ENTRIES = 60;
const TTL = 120_000;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  const cached = cache.get(path);
  if (cached && cached.expires > Date.now()) return cached.value as T;
  const response = await fetch(`/api${path}`, {
    signal,
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new ApiError(
      response.status === 404
        ? 'This record could not be found.'
        : 'The data service is unavailable. Please try again.',
      response.status,
    );
  }
  const value: T = await response.json();
  if (cache.size >= MAX_ENTRIES) cache.delete(cache.keys().next().value!);
  cache.set(path, { value, expires: Date.now() + TTL });
  return value;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Unable to load data. Please try again.';
}
export function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}
