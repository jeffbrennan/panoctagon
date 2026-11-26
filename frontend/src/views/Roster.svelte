<script lang="ts">
  import { onDestroy } from 'svelte';
  import { createRefresh } from '../lib/refresh';
  import { api, errorMessage } from '../lib/api';
  import type { RosterAnalytics } from '../lib/types';
  import { divisions, fighterHref, label, number } from '../lib/format';
  import { strikingType, strikeTargets, discrepancy } from '../lib/rosterCharts';
  import Chart from '../lib/Chart.svelte';
  import State from '../lib/State.svelte';
  let { openFighter, active, refresh }: { openFighter: (uid: string) => void; active: boolean; refresh: number } = $props();
  let division = $state('MIDDLEWEIGHT');
  let data = $state.raw<RosterAnalytics | null>(null);
  let loading = $state(true);
  let error = $state('');
  let retry = $state(0);
  let strikingOption = $derived(strikingType(data?.fighters || []));
  let targetOption = $derived(strikeTargets(data?.targets || []));
  let metric = $state('Age');
  let advantageOption = $derived(discrepancy(data?.advantages || [], metric));
  let search = $state('');
  let sort = $state('total_fights');
  let descending = $state(true);
  let page = $state(0);
  const pageSize = 20;
  let filtered = $derived.by(() => {
    const rows = (data?.fighters || []).filter((f) =>
      f.fighter_name.toLowerCase().includes(search.toLowerCase()),
    );
    return rows.sort((a, b) => {
      const av =
        sort === 'fighter_name'
          ? a.fighter_name
          : sort === 'win_rate'
            ? a.wins / a.total_fights
            : a[sort as 'landed' | 'absorbed' | 'total_fights' | 'opposition_strength'];
      const bv =
        sort === 'fighter_name'
          ? b.fighter_name
          : sort === 'win_rate'
            ? b.wins / b.total_fights
            : b[sort as 'landed' | 'absorbed' | 'total_fights' | 'opposition_strength'];
      return (
        (typeof av === 'string' && typeof bv === 'string'
          ? av.localeCompare(bv)
          : Number(av) - Number(bv)) * (descending ? -1 : 1)
      );
    });
  });
  let pageCount = $derived(Math.max(1, Math.ceil(filtered.length / pageSize)));
  let currentPage = $derived(Math.min(page, pageCount - 1));
  let visible = $derived(filtered.slice(currentPage * pageSize, (currentPage + 1) * pageSize));
  $effect(() => {
    search;
    division;
    sort;
    descending;
    page = 0;
  });
  function toggleSort(key: string) {
    if (sort === key) descending = !descending;
    else {
      sort = key;
      descending = key !== 'fighter_name';
    }
  }
  let lastRetry = 0;
  const request = createRefresh<RosterAnalytics>({
    load: (key, signal, bypass) => api(key, signal, bypass),
    success: (value) => { data = value; error = ''; },
    failure: (e) => (error = errorMessage(e)),
    loading: (value) => (loading = value),
  });
  $effect(() => {
    refresh;
    const force = retry !== lastRetry;
    lastRetry = retry;
    request.update(`/analytics/roster?division=${division}`, active, force);
  });
  onDestroy(request.cancel);
</script>

<div class="page-heading">
  <div>
    <h1>Roster</h1>
  </div>
  <span class="count-label">Minimum 5 UFC fights</span>
</div>
<div class="controls">
  <label class="field"
    >Division<select bind:value={division}
      ><option value="ALL">All divisions</option>{#each divisions as d}<option value={d}
          >{label(d)}</option
        >{/each}</select
    ></label
  ><span class="count-label"
    >{loading ? 'Updating…' : `${data?.fighters.length || 0} fighters`}</span
  >
</div>
{#if error && data}<p role="alert">Could not update data: {error} <button onclick={() => retry++}>Retry</button></p>{/if}
{#if error && !data}<State title="Unable to load roster statistics" message={error} retry={() => retry++} />
{:else if !data && loading}<State loading message="Loading roster analytics…" />
{:else if data}
  <div aria-busy={loading} class:updating={loading}>
    {#if !data.fighters.length}<State
        title="No qualifying fighters"
        message="Try another division to see fighters with at least five UFC appearances."
      />
    {:else}
      <div class="chart-grid">
        <section class="panel full">
          <div class="panel-heading">
            <div>
              <h2>Striking type</h2>
              <p>Strikes landed vs. absorbed per round. Larger circles = more fights.</p>
            </div>
          </div>
          <Chart
            family="roster"
            option={strikingOption}
            label={`Striking styles of ${data.fighters.length} fighters in ${label(division)}`}
            height={440}
            onselect={(point) => {
              if (point?.fighter) openFighter(point.fighter.fighter_uid);
            }}
          />
        </section>
        <section class="panel">
          <div class="panel-heading">
            <div>
              <h2>Striking target vs. result</h2>
              <p>Distribution of significant strikes by target</p>
            </div>
          </div>
          <Chart
            family="roster"
            option={targetOption}
            label="Head, body, and leg strike percentages for wins and losses"
            height={340}
            onselect={(point) => {
              if (point?.outlier) openFighter(point.outlier.fighter_uid);
            }}
          />
        </section>
        <section class="panel">
          <div class="panel-heading">
            <div>
              <h2>Matchup discrepancy</h2>
              <p>At least 20 appearances in each group</p>
            </div>
          </div>
          <label class="field inline discrepancy-control"
            >Advantage<select bind:value={metric}
              >{#each ['Age', 'Reach', 'Experience'] as m}<option value={m}>{m}</option
                >{/each}</select
            ></label
          ><Chart
            family="roster"
            option={advantageOption}
            label={`Win rate by ${metric.toLowerCase()} difference`}
            height={284}
          />
        </section>
      </div>
      <section class="roster-table-section">
        <div class="section-toolbar">
          <h2>Fighters <span class="muted">/ {filtered.length}</span></h2>
          <label class="field inline"
            >Search<input type="search" placeholder="Filter by name…" bind:value={search} /></label
          >
        </div>
        <!-- svelte-ignore a11y_no_noninteractive_tabindex (Scrollable tables need keyboard access.) -->
        <div class="table-scroll roster-scroll" tabindex="0" role="region" aria-label="Roster statistics">
          <!-- svelte-ignore a11y_no_redundant_roles (Explicit roles preserve table semantics when mobile CSS changes display.) -->
          <table class="data-table roster-table" role="table">
            <thead role="rowgroup"
              ><tr role="row"
                >{#each [['fighter_name', 'Fighter'], ['total_fights', 'Fights'], ['win_rate', 'Win %'], ['landed', 'Landed / round'], ['absorbed', 'Absorbed / round'], ['opposition_strength', 'Opposition']] as [key, title]}<th
                    role="columnheader"
                    aria-sort={sort === key ? (descending ? 'descending' : 'ascending') : 'none'}
                    ><button onclick={() => toggleSort(key)}
                      >{title}{sort === key ? (descending ? ' ↓' : ' ↑') : ''}</button
                    ></th
                  >{/each}</tr
              ></thead
            ><tbody role="rowgroup"
              >{#each visible as f (f.fighter_uid)}<tr role="row"
                  ><td role="cell" class="col-fighter"
                    ><a href={fighterHref(f.fighter_uid)} data-fighter={f.fighter_uid}
                      >{f.fighter_name}</a
                    ></td
                  ><td role="cell" class="col-fights" data-label="Fights">{f.total_fights}</td><td role="cell" class="col-winrate" data-label="Win %">{Math.round((f.wins / f.total_fights) * 100)}%</td
                  ><td role="cell" class="col-landed" data-label="Land/rd">{number(f.landed, 1)}</td><td role="cell" class="col-absorbed" data-label="Abs/rd">{number(f.absorbed, 1)}</td><td role="cell" class="col-opp" data-label="Opp."
                    >{f.opposition_strength}</td
                  ></tr
                >{:else}<tr role="row" class="empty-row"><td role="cell" colspan="6">No fighters match “{search}”.</td></tr>{/each}</tbody
            >
          </table>
        </div>
        <nav class="pagination" aria-label="Roster pages">
          <span aria-live="polite"
            >{filtered.length ? currentPage * pageSize + 1 : 0}–{Math.min(
              (currentPage + 1) * pageSize,
              filtered.length,
            )} of {filtered.length}</span
          >
          <div>
            <button
              class="button secondary"
              disabled={currentPage === 0}
              onclick={() => (page = currentPage - 1)}>Previous</button
            ><button
              class="button secondary"
              disabled={currentPage >= pageCount - 1}
              onclick={() => (page = currentPage + 1)}>Next</button
            >
          </div>
        </nav>
        <p class="table-note">
          Opposition strength: total UFC wins held by opponents a fighter has beaten.
        </p>
      </section>
    {/if}
  </div>
{/if}

<style>
  .pagination {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-top: 14px;
    font-size: 0.75rem;
    color: var(--muted);
  }
  .pagination > div {
    display: flex;
    gap: 8px;
  }
  .pagination .button {
    font-size: 0.75rem;
    padding: 8px 12px;
  }
  .updating {
    opacity: 0.55;
    pointer-events: none;
    transition: opacity 120ms ease;
  }
  .roster-table-section {
    margin-top: 32px;
  }
  .roster-table-section input {
    max-width: 260px;
    background: var(--surface);
    border: 2px solid var(--ink);
    padding: 10px 12px;
    border-radius: 2px;
    min-height: 44px;
    color: var(--ink);
  }
  .table-note {
    font-size: 0.75rem;
    color: var(--muted);
    margin-top: 12px;
  }
  .discrepancy-control {
    margin-bottom: 12px;
  }
  .controls {
    align-items: center;
  }
  .controls > .field {
    width: 260px;
  }
  @media (max-width: 640px) {
    .page-heading {
      flex-direction: column;
      align-items: flex-start;
      gap: 10px;
    }
    .controls > .field {
      width: 100%;
    }
    .roster-table-section input {
      width: 100%;
      max-width: 240px;
      font-size: 1rem;
    }
    .roster-scroll {
      overflow: visible;
      border: 0;
      background: transparent;
    }
    .roster-table {
      display: block;
      white-space: normal;
    }
    .roster-table thead {
      display: block;
      margin-bottom: 12px;
    }
    .roster-table thead tr {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .roster-table thead th {
      display: block;
      padding: 0;
      background: transparent;
      color: var(--ink);
    }
    .roster-table thead th button {
      display: inline-flex;
      align-items: center;
      min-height: 44px;
      padding: 8px 10px;
      border: 2px solid var(--ink);
      border-radius: 2px;
      background: var(--surface);
      color: var(--ink);
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: none;
      letter-spacing: 0;
      transition:
        background-color 140ms ease,
        color 140ms ease,
        border-color 140ms ease;
    }
    .roster-table thead th button:hover {
      border-color: var(--accent);
      color: var(--accent);
      text-decoration: none;
    }
    .roster-table thead th[aria-sort='ascending'] button,
    .roster-table thead th[aria-sort='descending'] button {
      background: var(--ink);
      color: var(--bg);
      border-color: var(--ink);
      font-weight: 700;
    }
    .roster-table tbody {
      display: grid;
      gap: 10px;
    }
    .roster-table tbody tr {
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 10px 6px;
      align-items: baseline;
      background: var(--surface);
      border: 2px solid var(--ink);
      border-radius: 2px;
      padding: 12px 14px;
    }
    .roster-table tbody tr:hover td {
      background: transparent;
    }
    .roster-table td {
      display: block;
      padding: 0;
      border: 0;
      min-width: 0;
    }
    .roster-table .col-fighter {
      grid-column: 1 / 9;
      grid-row: 1;
      font-size: 0.9375rem;
      overflow-wrap: anywhere;
    }
    .roster-table .col-winrate {
      grid-column: 9 / 13;
      grid-row: 1;
      text-align: right;
      font-size: 0.9375rem;
      font-weight: 700;
    }
    .roster-table .col-winrate::before {
      content: 'WIN ';
      font-size: 0.6875rem;
      font-weight: 600;
      color: var(--muted);
      letter-spacing: 0.04em;
    }
    .roster-table .col-fights,
    .roster-table .col-landed,
    .roster-table .col-absorbed,
    .roster-table .col-opp {
      grid-row: 2;
      border-top: 1px solid var(--line);
      padding-top: 8px;
      font-weight: 600;
    }
    .roster-table .col-fights {
      grid-column: 1 / 4;
    }
    .roster-table .col-landed {
      grid-column: 4 / 7;
    }
    .roster-table .col-absorbed {
      grid-column: 7 / 10;
    }
    .roster-table .col-opp {
      grid-column: 10 / 13;
      text-align: right;
    }
    .roster-table .col-fights::before,
    .roster-table .col-landed::before,
    .roster-table .col-absorbed::before,
    .roster-table .col-opp::before {
      content: attr(data-label);
      display: block;
      font-size: 0.6875rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
      margin-bottom: 2px;
    }
    .roster-table .empty-row td {
      grid-column: 1 / -1;
      color: var(--muted);
    }
  }
</style>
