<script lang="ts">
  import { api, errorMessage, isAbort } from '../lib/api';
  import type { RosterAnalytics } from '../lib/types';
  import { divisions, fighterHref, label, number } from '../lib/format';
  import { strikingType, strikeTargets, discrepancy } from '../lib/rosterCharts';
  import Chart from '../lib/Chart.svelte';
  import State from '../lib/State.svelte';
  let { openFighter }: { openFighter: (uid: string) => void } = $props();
  let division = $state('MIDDLEWEIGHT');
  let data = $state<RosterAnalytics | null>(null);
  let loading = $state(true);
  let error = $state('');
  let retry = $state(0);
  let metric = $state('Age');
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
  $effect(() => {
    const d = division;
    retry;
    const controller = new AbortController();
    loading = true;
    error = '';
    void api<RosterAnalytics>(`/analytics/roster?division=${d}`, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) data = value;
      })
      .catch((e) => {
        if (!isAbort(e)) error = errorMessage(e);
      })
      .finally(() => {
        if (!controller.signal.aborted) loading = false;
      });
    return () => controller.abort();
  });
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
{#if error}<State title="Unable to load roster statistics" message={error} retry={() => retry++} />
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
            option={strikingType(data.fighters)}
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
            option={strikeTargets(data.targets)}
            label="Head, body, and leg strike percentages for wins and losses"
            height={340}
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
            option={discrepancy(data.advantages, metric)}
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
        <div class="table-scroll" tabindex="0" role="region" aria-label="Roster statistics">
          <table class="data-table">
            <thead
              ><tr
                >{#each [['fighter_name', 'Fighter'], ['total_fights', 'Fights'], ['win_rate', 'Win %'], ['landed', 'Landed / round'], ['absorbed', 'Absorbed / round'], ['opposition_strength', 'Opposition']] as [key, title]}<th
                    aria-sort={sort === key ? (descending ? 'descending' : 'ascending') : 'none'}
                    ><button onclick={() => toggleSort(key)}
                      >{title}{sort === key ? (descending ? ' ↓' : ' ↑') : ''}</button
                    ></th
                  >{/each}</tr
              ></thead
            ><tbody
              >{#each visible as f (f.fighter_uid)}<tr
                  ><td
                    ><a href={fighterHref(f.fighter_uid)} data-fighter={f.fighter_uid}
                      >{f.fighter_name}</a
                    ></td
                  ><td>{f.total_fights}</td><td>{Math.round((f.wins / f.total_fights) * 100)}%</td
                  ><td>{number(f.landed, 1)}</td><td>{number(f.absorbed, 1)}</td><td
                    >{f.opposition_strength}</td
                  ></tr
                >{:else}<tr><td colspan="6">No fighters match “{search}”.</td></tr>{/each}</tbody
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
    border: 1px solid var(--line);
    padding: 10px 12px;
    border-radius: 3px;
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
    }
  }
</style>
