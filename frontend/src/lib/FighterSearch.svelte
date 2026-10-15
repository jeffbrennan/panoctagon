<script lang="ts">
  import { onDestroy } from 'svelte';
  import { api, errorMessage, isAbort } from './api';
  import type { FighterSummary } from './types';
  import { label } from './format';
  let { onselect }: { onselect: (uid: string) => void } = $props();
  let query = $state('');
  let results = $state<FighterSummary[]>([]);
  let open = $state(false);
  let loading = $state(false);
  let error = $state('');
  let selected = $state(-1);
  let root: HTMLDivElement;
  let input: HTMLInputElement;
  let controller: AbortController | undefined;
  let timer: ReturnType<typeof setTimeout>;
  let request = 0;

  $effect(() => {
    const term = query.trim();
    controller?.abort();
    clearTimeout(timer);
    const sequence = ++request;
    if (!open) return;
    loading = true;
    error = '';
    results = [];
    selected = -1;
    timer = setTimeout(
      async () => {
        const abort = new AbortController();
        controller = abort;
        try {
          const value = await api<FighterSummary[]>(
            `/fighter?limit=20${term ? `&name=${encodeURIComponent(term)}` : ''}`,
            abort.signal,
          );
          if (sequence === request) {
            results = value;
            selected = -1;
          }
        } catch (e) {
          if (!isAbort(e) && sequence === request) {
            results = [];
            error = errorMessage(e);
          }
        } finally {
          if (sequence === request) loading = false;
        }
      },
      term ? 180 : 0,
    );
    return () => {
      clearTimeout(timer);
      controller?.abort();
    };
  });
  onDestroy(() => {
    clearTimeout(timer);
    controller?.abort();
  });
  function choose(uid: string) {
    open = false;
    query = '';
    onselect(uid);
    input.blur();
  }
  function keys(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      open = false;
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      open = true;
      selected = Math.min(selected + 1, results.length - 1);
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      selected = results.length ? Math.max(selected - 1, 0) : -1;
    }
    if (event.key === 'Enter' && open && !loading && selected >= 0 && selected < results.length) {
      event.preventDefault();
      choose(results[selected].fighter_uid);
    }
    if (selected >= 0)
      requestAnimationFrame(() =>
        document.getElementById(`fighter-result-${selected}`)?.scrollIntoView({ block: 'nearest' }),
      );
  }
</script>

<svelte:window
  onpointerdown={(e) => {
    if (root && !root.contains(e.target as Node)) open = false;
  }}
/>
<div
  class="fighter-search"
  bind:this={root}
  onfocusout={(event) => {
    if (!root.contains(event.relatedTarget as Node)) open = false;
  }}
>
  <label class="field" for="fighter-search">Find a fighter</label>
  <div class="search-input-wrap">
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.5"
      aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></svg
    ><input
      id="fighter-search"
      role="combobox"
      aria-expanded={open}
      aria-controls="fighter-results"
      aria-autocomplete="list"
      aria-activedescendant={selected >= 0 && open ? `fighter-result-${selected}` : undefined}
      autocomplete="off"
      placeholder="Search fighters…"
      bind:value={query}
      bind:this={input}
      onfocus={() => (open = true)}
      onkeydown={keys}
    />
  </div>
  {#if open}
    <div class="search-results">
      {#if loading}<p class="search-status" role="status">Searching…</p>{/if}
      {#if error}<p class="search-status" role="alert">
          {error}
        </p>{:else if !loading && !results.length}<p class="search-status">
          No fighters found.
        </p>{/if}
      <ul
        id="fighter-results"
        role="listbox"
        tabindex="0"
        onkeydown={keys}
        aria-label="Fighters"
        aria-busy={loading}
      >
        {#each results as f, i (f.fighter_uid)}
          <li role="presentation">
            <button
              role="option"
              aria-selected={selected === i}
              id={`fighter-result-${i}`}
              tabindex="-1"
              class:selected={selected === i}
              onclick={() => choose(f.fighter_uid)}
              ><span><strong>{f.full_name}</strong><small>{label(f.division)}</small></span><span
                class="record">{f.wins}-{f.losses}-{f.draws}</span
              ></button
            >
          </li>
        {/each}
      </ul>
    </div>
  {/if}
</div>

<style>
  .fighter-search {
    position: relative;
    width: 360px;
    max-width: 100%;
    z-index: 10;
  }
  .fighter-search > .field {
    margin-bottom: 8px;
  }
  .search-input-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
    border: 1px solid var(--line);
    border-radius: 3px;
    background: var(--surface);
    padding: 0 12px;
  }
  .search-input-wrap svg {
    color: var(--muted);
    flex-shrink: 0;
  }
  .search-input-wrap:focus-within {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .search-input-wrap input {
    padding: 11px 0;
    min-width: 0;
    width: 100%;
    border: 0;
    background: transparent;
    outline: none;
    font-size: 0.8125rem;
  }
  .search-results {
    position: absolute;
    left: 0;
    right: 0;
    top: calc(100% + 6px);
    border: 1px solid var(--line);
    background: var(--surface);
    box-shadow: 0 12px 30px #1a1a1a12;
    border-radius: 3px;
  }
  .search-results ul {
    list-style: none;
    padding: 0;
    margin: 0;
    max-height: 340px;
    overflow: auto;
  }
  .search-results button {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    gap: 12px;
    border: 0;
    border-bottom: 1px solid var(--line);
    background: transparent;
    text-align: left;
    padding: 12px 14px;
  }
  .search-results button:hover,
  .search-results button.selected {
    background: #e8e6da;
  }
  .search-results strong {
    display: block;
    font-size: 0.8125rem;
    font-weight: 600;
  }
  .search-results small {
    display: block;
    color: var(--muted);
    font-size: 0.75rem;
  }
  .search-status {
    font-size: 0.75rem;
    color: var(--muted);
    padding: 14px;
  }
  .search-results .record {
    white-space: nowrap;
    font-size: 0.75rem;
  }
  @media (max-width: 640px) {
    .fighter-search {
      width: 100%;
    }
  }
</style>
