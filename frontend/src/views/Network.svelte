<script lang="ts">
  import type { EChartsOption } from 'echarts';
  import { api, errorMessage, isAbort } from '../lib/api';
  import type { Metadata, NetworkData } from '../lib/types';
  import { divisions, label } from '../lib/format';
  import { baseOption } from '../lib/chartTheme';
  import State from '../lib/State.svelte';
  import Chart from '../lib/Chart.svelte';
  let { metadata, openFighter }: { metadata: Metadata | null; openFighter: (uid: string) => void } =
    $props();
  let division = $state('HEAVYWEIGHT');
  let start = $state(2021);
  let end = $state(2026);
  let loading = $state(true);
  let error = $state('');
  let data = $state<NetworkData | null>(null);
  let selected = $state('');
  let focus = $state(false);
  let retry = $state(0);
  let minYear = $derived(metadata?.first_year || 1993);
  let maxYear = $derived(Math.max(metadata?.last_year || 2026, new Date().getFullYear()));
  let years = $derived(Array.from({ length: maxYear - minYear + 1 }, (_, i) => minYear + i));
  let selectedNode = $derived(data?.nodes.find((n) => n.id === selected));
  let shown = $derived.by(() => {
    if (!data || !focus || !selected) return data;
    const neighbors = new Set([selected]);
    data.links.forEach((l) => {
      if (l.source === selected) neighbors.add(l.target);
      if (l.target === selected) neighbors.add(l.source);
    });
    return {
      nodes: data.nodes.filter((n) => neighbors.has(n.id)),
      links: data.links.filter((l) => neighbors.has(l.source) && neighbors.has(l.target)),
    };
  });
  let option = $derived<EChartsOption>({
    ...baseOption,
    tooltip: {
      ...baseOption.tooltip,
      trigger: 'item',
      formatter: (params: any) =>
        params.dataType === 'edge'
          ? `${params.data.fights} ${params.data.fights === 1 ? 'fight' : 'fights'}`
          : `${params.data.name}\n${params.data.wins} wins · ${params.data.losses} losses\n${params.data.fights} fights in selected period\nClick to select fighter`,
    },
    animationDurationUpdate: 220,
    series: [
      {
        type: 'graph',
        layout: 'none',
        roam: true,
        scaleLimit: { min: 0.4, max: 6 },
        draggable: false,
        data: shown?.nodes.map((n) => ({
          ...n,
          symbolSize: Math.min(12 + Math.sqrt(n.fights) * 5, 40),
          value: n.fights,
          itemStyle: {
            color: selected === n.id ? '#34574a' : '#4c5347',
            borderColor: selected === n.id ? '#f2f0e3' : '#f2f0e3',
            borderWidth: selected === n.id ? 3 : 1.5,
          },
          label: {
            show: n.fights >= 10 || selected === n.id || !!(focus && selected),
            position: 'bottom',
            fontSize: 10,
            color: '#4b4f43',
          },
        })),
        links: shown?.links.map((l) => ({
          ...l,
          lineStyle: {
            width: l.fights > 1 ? 2 : 1,
            opacity: selected && (l.source === selected || l.target === selected) ? 0.9 : 0.2,
          },
        })),
        emphasis: {
          focus: 'adjacency',
          label: { show: true },
          lineStyle: { opacity: 0.8, width: 2 },
        },
        blur: { itemStyle: { opacity: 0.2 }, lineStyle: { opacity: 0.05 } },
        lineStyle: { color: '#777d6c', curveness: 0.06 },
      },
    ],
  });
  $effect(() => {
    const d = division,
      a = start,
      b = end;
    retry;
    const controller = new AbortController();
    loading = true;
    error = '';
    const timer = setTimeout(async () => {
      try {
        const value = await api<NetworkData>(
          `/analytics/network?division=${d}&start_year=${a}&end_year=${b}`,
          controller.signal,
        );
        if (!controller.signal.aborted) {
          data = value;
          selected = '';
          focus = false;
        }
      } catch (e) {
        if (!isAbort(e)) error = errorMessage(e);
      } finally {
        if (!controller.signal.aborted) loading = false;
      }
    }, 120);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  });
</script>

<div class="page-heading">
  <div>
    <h1>Network</h1>
  </div>
  <span class="count-label"
    >{data?.nodes.length || 0} fighters · {data?.links.length || 0} matchups</span
  >
</div>
<div class="controls">
  <label class="field"
    >Division<select bind:value={division}
      >{#each divisions as d}<option value={d}>{label(d)}</option>{/each}</select
    ></label
  ><label class="field year-field"
    >From<select
      bind:value={start}
      onchange={() => {
        if (start > end) end = start;
      }}
      >{#each years as year}<option value={year}>{year}</option>{/each}</select
    ></label
  ><label class="field year-field"
    >Through<select
      bind:value={end}
      onchange={() => {
        if (end < start) start = end;
      }}
      >{#each years as year}<option value={year}>{year}</option>{/each}</select
    ></label
  >
</div>
{#if error}<State title="Unable to load the network" message={error} retry={() => retry++} />
{:else if !data && loading}<State loading message="Building fighter connections…" />
{:else if data && !data.nodes.length}<State
    title="No connections in this period"
    message="Try another division or a wider year range."
  />
{:else if data}
  <section class="panel network-panel" aria-busy={loading}>
    <div class="panel-heading">
      <div>
        <h2>{label(division)}</h2>
        <p>
          {loading
            ? 'Updating network…'
            : `${start}–${end} · Drag to pan. Scroll or pinch to zoom.`}
        </p>
      </div>
      <button
        class="button secondary"
        onclick={() => {
          selected = '';
          focus = false;
        }}>Reset selection</button
      >
    </div>
    <div class="network-toolbar">
      <label class="field"
        >Select a fighter<select bind:value={selected}
          ><option value="">All connections</option
          >{#each [...data.nodes].sort((a, b) => a.name.localeCompare(b.name)) as node}<option
              value={node.id}>{node.name}</option
            >{/each}</select
        ></label
      ><label class="focus-toggle"
        ><input type="checkbox" bind:checked={focus} disabled={!selected} /> Opponents only</label
      >
    </div>
    <div class="network-graph" class:updating={loading}>
      <Chart
        {option}
        label={`Network of ${shown?.nodes.length} UFC fighters in ${label(division)}, from ${start} through ${end}`}
        height={500}
        onselect={(node) => {
          if (node?.id) selected = node.id;
        }}
      />
    </div>
    <div class="network-detail" aria-live="polite">
      {#if selectedNode}<div>
          <strong>{selectedNode.name}</strong><span
            >{selectedNode.wins} wins · {selectedNode.losses} losses · {selectedNode.fights} fights in
            period</span
          >
        </div>
        <button class="button" onclick={() => openFighter(selected)}>View profile</button>{:else}<p>
          Select a fighter to highlight their connections and explore their profile.
        </p>
        <span class="count-label">Larger node = more fights</span>{/if}
    </div>
  </section>
{/if}

<style>
  .controls > .year-field {
    min-width: 120px;
  }
  .network-toolbar {
    display: flex;
    gap: 24px;
    align-items: flex-end;
    border-bottom: 1px solid var(--line);
    padding-bottom: 18px;
  }
  .network-toolbar > .field {
    width: 300px;
    max-width: 100%;
  }
  .focus-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.75rem;
    min-height: 44px;
  }
  .focus-toggle input {
    width: 16px;
    height: 16px;
    accent-color: var(--ink);
  }
  .network-graph {
    transition: opacity 160ms ease;
  }
  .network-graph.updating {
    opacity: 0.5;
    pointer-events: none;
  }
  .network-detail {
    border-top: 1px solid var(--line);
    padding-top: 18px;
    display: flex;
    justify-content: space-between;
    gap: 20px;
    align-items: center;
    min-height: 64px;
  }
  .network-detail strong {
    display: block;
    font-size: 0.875rem;
  }
  .network-detail span,
  .network-detail p {
    font-size: 0.75rem;
    color: var(--muted);
  }
  @media (max-width: 640px) {
    .page-heading {
      align-items: flex-start;
      flex-direction: column;
    }
    .controls > .year-field {
      min-width: 100px;
    }
    .controls > .field:first-child {
      flex-basis: 100%;
    }
    .network-toolbar {
      gap: 10px;
      flex-direction: column;
      align-items: flex-start;
    }
    .network-toolbar > .field {
      width: 100%;
    }
    .network-detail {
      flex-direction: column;
      align-items: flex-start;
      gap: 12px;
    }
    .network-panel > .panel-heading {
      align-items: flex-start;
    }
    .network-panel > .panel-heading > .button {
      font-size: 0.625rem;
      padding: 8px;
    }
    .network-graph {
      margin: 0 -8px;
    }
  }
</style>
