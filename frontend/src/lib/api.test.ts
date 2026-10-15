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
    const fetch = vi.fn().mockRejectedValue(new DOMException('Aborted', 'AbortError'));
    vi.stubGlobal('fetch', fetch);
    const { api, isAbort } = await import('./api');
    const controller = new AbortController();
    controller.abort();
    await expect(api('/fighter', controller.signal)).rejects.toSatisfy(isAbort);
    expect(fetch).toHaveBeenCalledWith(
      '/api/fighter',
      expect.objectContaining({ signal: controller.signal }),
    );
  });
});
