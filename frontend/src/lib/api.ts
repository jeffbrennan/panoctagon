let generation = 0;
const cache = new Map<string, { value: unknown; expires: number }>();
const inflight = new Map<string, Promise<unknown>>();
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

export function invalidateCache(): void {
  cache.clear();
  inflight.clear();
  generation++;
}
export function cacheGeneration(): number { return generation; }

export function isFresh(path: string): boolean {
  return (cache.get(path)?.expires ?? 0) > Date.now();
}

function store(path: string, value: unknown, startGeneration: number): void {
  if (generation !== startGeneration) return;
  if (cache.size >= MAX_ENTRIES) cache.delete(cache.keys().next().value!);
  cache.set(path, { value, expires: Date.now() + TTL });
}

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const startGeneration = generation;
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
  signal?.throwIfAborted();
  store(path, value, startGeneration);
  return value;
}

function withSignal<T>(promise: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) return promise;
  signal.throwIfAborted();
  return new Promise<T>((resolve, reject) => {
    const onAbort = () => reject(signal.reason);
    signal.addEventListener('abort', onAbort, { once: true });
    promise.then(
      (value) => {
        signal.removeEventListener('abort', onAbort);
        resolve(value);
      },
      (error) => {
        signal.removeEventListener('abort', onAbort);
        reject(error);
      },
    );
  });
}

/** Starts a non-blocking GET for an explicitly requested view so it overlaps module load. */
export function warmApi(path: string): void {
  if (isFresh(path) || inflight.has(path)) return;
  const pending = fetchJson(path).finally(() => {
    if (inflight.get(path) === pending) inflight.delete(path);
  });
  inflight.set(path, pending);
  void pending.catch(() => {});
}

export async function api<T>(path: string, signal?: AbortSignal, bypass = false): Promise<T> {
  signal?.throwIfAborted();
  const cached = cache.get(path);
  if (!bypass && cached && cached.expires > Date.now()) return cached.value as T;
  if (!bypass) {
    const pending = inflight.get(path);
    if (pending) return withSignal(pending as Promise<T>, signal);
  }
  return fetchJson<T>(path, signal);
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Unable to load data. Please try again.';
}
export function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}
