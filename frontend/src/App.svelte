<script lang="ts">
  import { onMount } from 'svelte';
  import type { Component } from 'svelte';
  import type { Metadata, View } from './lib/types';
  import { api } from './lib/api';
  import State from './lib/State.svelte';
  import Upcoming from './views/Upcoming.svelte';

  const views: View[] = ['upcoming', 'fighters', 'network', 'roster'];
  const names = {
    upcoming: 'Upcoming',
    fighters: 'Fighters',
    network: 'Network',
    roster: 'Roster',
  };
  const loaders = {
    fighters: () => import('./views/Fighters.svelte'),
    network: () => import('./views/Network.svelte'),
    roster: () => import('./views/Roster.svelte'),
  };
  const modules = new Map<string, Component<any>>();
  const initialParams = new URLSearchParams(location.search);
  const requestedView = initialParams.get('view') as View;
  const initialView: View = views.includes(requestedView) ? requestedView : 'upcoming';
  let view = $state<View>(initialView);
  let pages = $state<Partial<Record<View, Component<any>>>>(
    initialView === 'upcoming' ? { upcoming: Upcoming } : {},
  );
  let viewError = $state(false);
  let loading = $state(initialView !== 'upcoming');
  let metadata = $state.raw<Metadata | null>(null);
  let fighter = $state(initialParams.get('fighter') || '');
  let sequence = 0;

  async function show(next: View, uid?: string, push = true) {
    view = next;
    if (next === 'fighters' && uid !== undefined) fighter = uid;
    viewError = false;
    const current = ++sequence;
    if (push) {
      const params = new URLSearchParams();
      if (next !== 'upcoming') params.set('view', next);
      if (next === 'fighters' && fighter) params.set('fighter', fighter);
      history.pushState(null, '', `${location.pathname}${params.size ? `?${params}` : ''}`);
    }
    document.title = `${names[next]} · Panoctagon`;
    if (next === 'upcoming') {
      pages.upcoming = Upcoming;
      loading = false;
      return;
    }
    const existing = modules.get(next);
    if (existing) {
      pages[next] = existing;
      loading = false;
      return;
    }
    loading = true;
    try {
      const module = await loaders[next]();
      modules.set(next, module.default);
      if (current === sequence) pages[next] = module.default;
    } catch {
      if (current === sequence) viewError = true;
    } finally {
      if (current === sequence) loading = false;
    }
  }
  function readLocation() {
    const params = new URLSearchParams(location.search);
    const next = params.get('view') as View;
    void show(views.includes(next) ? next : 'upcoming', params.get('fighter') || '', false);
  }
  function openFighter(uid: string) {
    void show('fighters', uid);
    window.scrollTo({ top: 0, behavior: 'instant' });
    document.getElementById('main')?.focus({ preventScroll: true });
  }
  function follow(event: MouseEvent) {
    const target = (event.target as Element).closest<HTMLAnchorElement>('a[data-fighter]');
    if (
      target &&
      event.button === 0 &&
      !event.metaKey &&
      !event.ctrlKey &&
      !event.shiftKey &&
      !event.altKey
    ) {
      event.preventDefault();
      openFighter(target.dataset.fighter!);
    }
  }
  function prefetch(next: View) {
    if (next !== 'upcoming' && !modules.has(next))
      void loaders[next]()
        .then((module) => modules.set(next, module.default))
        .catch(() => {});
  }
  onMount(() => {
    readLocation();
    const controller = new AbortController();
    void api<Metadata>('/metadata', controller.signal)
      .then((value) => (metadata = value))
      .catch(() => {});
    document.addEventListener('click', follow);
    window.addEventListener('popstate', readLocation);
    return () => {
      controller.abort();
      document.removeEventListener('click', follow);
      window.removeEventListener('popstate', readLocation);
    };
  });
</script>

<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header">
  <div class="header-inner">
    <a
      class="wordmark"
      href="/"
      onclick={(event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        void show('upcoming');
      }}
      aria-label="Panoctagon home"
    >
      <svg viewBox="0 0 32 32" aria-hidden="true"
        ><path
          d="M10 2h12l8 8v12l-8 8H10l-8-8V10z"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        /><path
          d="M12 9h6a6 6 0 0 1 0 12h-3v5h-3zm3 3v6h3a3 3 0 0 0 0-6z"
          fill="currentColor"
        /></svg
      >
      panoctagon
    </a>
    <span class="refresh-label"
      >{metadata?.last_refresh
        ? `Data as of ${metadata.last_refresh.slice(0, 10)}`
        : 'UFC fight analytics'}</span
    >
  </div>
</header>
<div class="workspace">
  <nav class="main-nav" aria-label="Main navigation">
    {#each views as item}
      <a
        href={item === 'upcoming' ? '/' : `?view=${item}`}
        class:active={view === item}
        aria-current={view === item ? 'page' : undefined}
        onclick={(event) => {
          if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
          event.preventDefault();
          void show(item);
        }}
        onpointerenter={() => prefetch(item)}
        onfocus={() => prefetch(item)}>{names[item]}</a
      >
    {/each}
  </nav>
  <main id="main" tabindex="-1" aria-busy={loading}>
    {#if viewError}
      <State
        title="This view could not load"
        message="Check your connection and try again."
        retry={() => location.reload()}
      />
    {:else if loading}
      <State loading message={`Loading ${names[view].toLowerCase()}…`} />
    {/if}
    {#each views as item}
      {#if pages[item]}
        {@const Page = pages[item]!}
        <div class="view" hidden={view !== item}>
          <Page {fighter} {openFighter} {metadata} />
        </div>
      {/if}
    {/each}
  </main>
  <footer>
    <span>panoctagon</span><span
      >UFC records & statistics · <a href="https://ufcstats.com" target="_blank" rel="noreferrer"
        >UFC Stats</a
      ></span
    >
  </footer>
</div>
