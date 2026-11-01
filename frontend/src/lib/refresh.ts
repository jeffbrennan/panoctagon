import { isFresh, isAbort } from './api';

/** Coordinates a view's current request without tying the lifetime of its content to it. */
export function createRefresh<T>(handlers: {
  load: (key: string, signal: AbortSignal, bypass: boolean) => Promise<T>;
  success: (value: T, key: string) => void;
  failure: (error: unknown) => void;
  loading: (value: boolean) => void;
}) {
  let key = '';
  let successfulKey = '';
  let lastAttempt = 0;
  let controller: AbortController | undefined;
  let pending = false;

  function cancel() {
    if (pending) lastAttempt = 0;
    controller?.abort();
    controller = undefined;
    pending = false;
    handlers.loading(false);
  }
  function update(next: string, active: boolean, force = false) {
    if (!active) { cancel(); return; }
    if (key !== next) { cancel(); key = next; lastAttempt = 0; }
    if (pending) return;
    if (!force && successfulKey === key && isFresh(key)) return;
    if (!force && lastAttempt && Date.now() - lastAttempt < 120_000) return;
    const request = new AbortController();
    controller = request;
    pending = true;
    lastAttempt = Date.now();
    handlers.loading(true);
    void handlers.load(key, request.signal, force).then((value) => {
      if (!request.signal.aborted) { successfulKey = next; handlers.success(value, next); }
    }).catch((error) => {
      if (!request.signal.aborted && !isAbort(error)) handlers.failure(error);
    }).finally(() => {
      if (controller === request) { pending = false; handlers.loading(false); }
    });
  }
  return { update, cancel };
}
