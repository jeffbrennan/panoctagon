import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

beforeEach(() => {
  vi.resetModules();
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('API data cache', () => {
  it('reuses successful responses until they expire', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('[{"name":"Alex"}]', { status: 200 }));
    vi.stubGlobal('fetch', fetch);
    const { api } = await import('./api');
    expect(await api('/fighter')).toEqual([{ name: 'Alex' }]);
    expect(await api('/fighter')).toEqual([{ name: 'Alex' }]);
    expect(fetch).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(120_001);
    fetch.mockResolvedValue(new Response('[]', { status: 200 }));
    expect(await api('/fighter')).toEqual([]);
    expect(fetch).toHaveBeenCalledTimes(2);
  });
  it('does not cache failures, so retry can recover', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response('{}', { status: 503 }))
      .mockResolvedValueOnce(new Response('[]'));
    vi.stubGlobal('fetch', fetch);
    const { api, ApiError } = await import('./api');
    await expect(api('/upcoming')).rejects.toBeInstanceOf(ApiError);
    expect(await api('/upcoming')).toEqual([]);
    expect(fetch).toHaveBeenCalledTimes(2);
  });
  it('forwards cancellation and recognizes aborts', async () => {
    const fetch = vi.fn(
      (_url: string, { signal }: { signal: AbortSignal }) =>
        new Promise((_resolve, reject) => {
          signal.addEventListener('abort', () => reject(signal.reason), { once: true });
        }),
    );
    vi.stubGlobal('fetch', fetch);
    const { api, isAbort } = await import('./api');
    const controller = new AbortController();
    const pending = api('/fighter', controller.signal);
    controller.abort();
    await expect(pending).rejects.toSatisfy(isAbort);
    expect(fetch).toHaveBeenCalledWith(
      '/api/fighter',
      expect.objectContaining({ signal: controller.signal }),
    );
  });
});

it('honors cancellation even when the response is already cached', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('[]'));
  vi.stubGlobal('fetch', fetch);
  const { api, isAbort } = await import('./api');
  await api('/upcoming');
  const controller = new AbortController();
  controller.abort();
  await expect(api('/upcoming', controller.signal)).rejects.toSatisfy(isAbort);
  expect(fetch).toHaveBeenCalledTimes(1);
});

it('does not cache a response aborted while its body is being read', async () => {
  let finish!: (value: unknown) => void;
  const fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => new Promise((resolve) => (finish = resolve)),
  });
  vi.stubGlobal('fetch', fetch);
  const { api } = await import('./api');
  const controller = new AbortController();
  const pending = api('/upcoming', controller.signal);
  await Promise.resolve();
  controller.abort();
  finish([]);
  await expect(pending).rejects.toThrow();
  fetch.mockResolvedValueOnce(new Response('[1]'));
  expect(await api('/upcoming')).toEqual([1]);
});

it('allows an explicit cache bypass', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(new Response('[1]')).mockResolvedValueOnce(new Response('[2]'));
  vi.stubGlobal('fetch', fetch);
  const { api } = await import('./api');
  await api('/upcoming');
  expect(await api('/upcoming', undefined, true)).toEqual([2]);
});

it('reuses an in-flight warmed request while still respecting abort and cache invalidation', async () => {
  let finish!: (value: unknown) => void;
  const fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => new Promise((resolve) => (finish = resolve)),
  });
  vi.stubGlobal('fetch', fetch);
  const { api, warmApi, invalidateCache, isAbort } = await import('./api');
  warmApi('/analytics/roster?division=MIDDLEWEIGHT');
  const controller = new AbortController();
  const first = api('/analytics/roster?division=MIDDLEWEIGHT', controller.signal);
  expect(fetch).toHaveBeenCalledTimes(1);
  controller.abort();
  await expect(first).rejects.toSatisfy(isAbort);
  invalidateCache();
  finish({ stale: true });
  await Promise.resolve();
  fetch.mockResolvedValueOnce(new Response('{"fresh":true}'));
  expect(await api('/analytics/roster?division=MIDDLEWEIGHT')).toEqual({ fresh: true });
  expect(fetch).toHaveBeenCalledTimes(2);
});
