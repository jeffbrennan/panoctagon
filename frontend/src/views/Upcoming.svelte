<script lang="ts">
  import { onDestroy } from 'svelte';
  import { createRefresh } from '../lib/refresh';
  import { api, errorMessage } from '../lib/api';
  import type { UpcomingEvent } from '../lib/types';
  import { date, label } from '../lib/format';
  import State from '../lib/State.svelte';
  import MatchupCard from '../lib/MatchupCard.svelte';

  let { active, refresh }: { active: boolean; refresh: number } = $props();
  let loaded = $state(false);
  let refreshing = $state(false);
  let notice = $state('');
  let retry = $state(0);
  let lastRetry = 0;
  let events = $state.raw<UpcomingEvent[]>([]);
  let selected = $state('');
  let loading = $state(true);
  let error = $state('');
  let event = $derived(events.find((item) => item.event_uid === selected) || events[0]);
  let division = $state('ALL');
  let fights = $derived(
    event?.fights.filter((f) => division === 'ALL' || f.fight_division === division) || [],
  );
  let eventDivisions = $derived([
    ...new Set(event?.fights.map((f) => f.fight_division).filter((d): d is string => !!d)),
  ]);

  const request = createRefresh<UpcomingEvent[]>({
    load: (key, signal, bypass) => api(key, signal, bypass),
    success: (value) => {
      events = value;
      loaded = true;
      error = '';
      if (selected && !value.some((item) => item.event_uid === selected)) {
        selected = '';
        division = 'ALL';
        notice = 'The selected event is no longer available; showing the next event.';
      }
      const selectedEvent = value.find((item) => item.event_uid === selected) || value[0];
      if (division !== 'ALL' && !selectedEvent?.fights.some((fight) => fight.fight_division === division)) {
        division = 'ALL';
        notice = 'The selected division is no longer available; showing all divisions.';
      }
    },
    failure: (e) => (error = errorMessage(e)),
    loading: (value) => { refreshing = value; loading = value && !loaded; },
  });
  $effect(() => {
    refresh;
    const force = retry !== lastRetry;
    lastRetry = retry;
    request.update('/upcoming', active, force);
  });
  onDestroy(request.cancel);
</script>

<div class="page-heading">
  <div>
    <h1>Upcoming</h1>
  </div>
  <span class="count-label">{events.length} {events.length === 1 ? 'event' : 'events'}</span>
</div>
{#if notice}<p role="status">{notice}</p>{/if}
{#if loaded && refreshing}<p role="status">Refreshing upcoming events…</p>{/if}
{#if loaded && error}<p role="alert">Could not update upcoming events: {error} <button onclick={() => retry++}>Retry</button></p>{/if}
{#if loading}
  <div class="card-skeleton" aria-hidden="true"></div>
  <State loading message="Loading upcoming fights…" />
{:else if error && !loaded}
  <State title="Unable to load upcoming events" message={error} retry={() => retry++} />
{:else if events.length === 0}
  <State
    title="No upcoming events"
    message="No scheduled fights are available in the current dataset. You can still explore fighter careers and roster statistics."
  />
{:else}
  {#if events.length > 1}
    <label class="field event-select"
      >Event<select bind:value={selected} onchange={() => (division = 'ALL')}
        ><option value="">Next event</option>{#each events as item}<option value={item.event_uid}
            >{item.event_title} · {date(item.event_date, true)}</option
          >{/each}</select
      ></label
    >
  {/if}
  <section class="event-banner" aria-labelledby="event-title">
    <div class="date-block">
      <span
        >{new Date(`${event.event_date}T12:00:00Z`).toLocaleString('en-US', {
          month: 'short',
          timeZone: 'UTC',
        })}</span
      ><strong>{new Date(`${event.event_date}T12:00:00Z`).getUTCDate()}</strong>
    </div>
    <div class="event-info">
      <p class="eyebrow">Next in the octagon</p>
      <h2 id="event-title">{event.event_title}</h2>
      <p>{date(event.event_date)}<span class="separator">/</span>{event.event_location}</p>
    </div>
    <span class="badge">{event.fights.length} fights</span>
  </section>
  <div class="section-toolbar">
    <h2>Fight card <span class="muted">/ {fights.length}</span></h2>
    <label class="field inline"
      >Division<select bind:value={division}
        ><option value="ALL">All divisions</option>{#each eventDivisions as d}<option value={d}
            >{label(d)}</option
          >{/each}</select
      ></label
    >
  </div>
  <div class="fight-list">
    {#each fights as fight, index (fight.fight_uid)}
      <MatchupCard {fight} main={index === 0 && division === 'ALL'} />
    {/each}
  </div>
{/if}
