import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createRefresh } from './refresh';

beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(1_000_000); });
afterEach(() => { vi.useRealTimers(); });

it('coalesces triggers, cancels obsolete keys, and ignores their results', async () => {
  const requests: { key: string; signal: AbortSignal; resolve: (value: string) => void }[] = [];
  const success = vi.fn();
  const request = createRefresh<string>({
    load: (key, signal) => new Promise((resolve) => requests.push({ key, signal, resolve })),
    success,
    failure: vi.fn(),
    loading: vi.fn(),
  });
  request.update('/first', true);
  request.update('/first', true);
  expect(requests).toHaveLength(1);
  request.update('/second', true);
  expect(requests[0].signal.aborted).toBe(true);
  requests[0].resolve('obsolete');
  requests[1].resolve('current');
  await vi.waitFor(() => expect(success).toHaveBeenCalledWith('current', '/second'));
  expect(success).toHaveBeenCalledTimes(1);
});

it('throttles failed refreshes and allows an explicit retry', async () => {
  const load = vi.fn().mockRejectedValue(new Error('offline'));
  const failure = vi.fn();
  const request = createRefresh({ load, success: vi.fn(), failure, loading: vi.fn() });
  request.update('/data', true);
  await vi.waitFor(() => expect(failure).toHaveBeenCalled());
  await Promise.resolve();
  request.update('/data', true);
  expect(load).toHaveBeenCalledTimes(1);
  request.update('/data', true, true);
  expect(load).toHaveBeenCalledTimes(2);
});
