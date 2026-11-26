<script lang="ts">
  import { onMount } from 'svelte';
  import type { EChartsType } from 'echarts/core';
  import type { EChartsOption, GraphSeriesOption } from 'echarts';
  import { loadChart, type ChartFamily } from './chartLoader';
  let {
    option,
    label,
    height = 320,
    onselect,
    family = 'fighter',
  }: {
    option: EChartsOption;
    label: string;
    height?: number;
    onselect?: (data: any) => void;
    family?: ChartFamily;
  } = $props();
  let container: HTMLDivElement;
  let chart = $state<EChartsType | null>(null);
  let error = $state(false);
  let ready = $state(false);
  let reducedMotion = $state(false);
  let visible = $state(false);
  let observer: ResizeObserver;
  let frame = 0;
  let measuredWidth = 0;
  let measuredHeight = 0;
  let renderedOption: EChartsOption | undefined;
  let renderedLabel = '';
  let renderedMotion = false;
  // The release-gate harness opts in before page load; normal sessions do not
  // collect performance entries or expose benchmark state.
  const measuring = typeof window !== 'undefined' && Boolean((window as any).__chartPerformanceGate);
  function mark(stage: string) {
    if (measuring) performance.mark(`chart:${family}:${stage}`);
  }
  export function resetGraphView() {
    const series = (chart?.getOption().series as GraphSeriesOption[] | undefined)?.find(
      (series) => series.type === 'graph',
    );
    if (series) chart?.setOption({ series: [{ id: series.id, zoom: 1, center: ['50%', '50%'] }] });
  }
  function resizeChart() {
    if (!chart || !visible) return;
    const width = container.clientWidth,
      height = container.clientHeight;
    if (width > 0 && (width !== measuredWidth || height !== measuredHeight)) {
      mark('resize');
      chart.resize();
      measuredWidth = width;
      measuredHeight = height;
    }
  }

  onMount(() => {
    let disposed = false;
    let initializing = false;
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    reducedMotion = motion.matches;
    function updateMotion() {
      reducedMotion = motion.matches;
    }
    motion.addEventListener('change', updateMotion);
    const visibility = new IntersectionObserver(
      async (entries) => {
        if (disposed) return;
        visible = entries.some((entry) => entry.isIntersecting);
        mark(visible ? 'visible' : 'hidden');
        if (visible) chart?.getZr().animation.resume();
        else chart?.getZr().animation.pause();
        if (!visible || chart || initializing) return;
        initializing = true;
        try {
          mark('modules-start');
          const { init } = await loadChart(family);
          mark('modules-ready');
          if (disposed || !visible || container.clientWidth === 0) return;
          chart = init(container, undefined, {
            renderer: 'canvas',
            devicePixelRatio: Math.min(window.devicePixelRatio || 1, 2),
          });
          mark('initialized');
          measuredWidth = container.clientWidth;
          measuredHeight = container.clientHeight;
          chart.on('click', (params: any) => onselect?.(params.data));
          observer = new ResizeObserver(() => {
            cancelAnimationFrame(frame);
            frame = requestAnimationFrame(() => {
              resizeChart();
            });
          });
          observer.observe(container);
          ready = true;
        } catch {
          if (!disposed) error = true;
        } finally {
          initializing = false;
        }
      },
      { rootMargin: '150px' },
    );
    visibility.observe(container);
    return () => {
      disposed = true;
      visibility.disconnect();
      observer?.disconnect();
      cancelAnimationFrame(frame);
      motion.removeEventListener('change', updateMotion);
      chart?.dispose();
    };
  });
  $effect(() => {
    if (chart && visible) {
      resizeChart();
      const current = option;
      if (current !== renderedOption) {
        if (measuring) {
          delete container.dataset.gateRendered;
          const instance = chart;
          const onRendered = () => {
            instance.off('rendered', onRendered);
            requestAnimationFrame(() => {
              if (chart === instance && renderedOption === current) {
                container.dataset.gateRendered = 'true';
                mark('data-frame');
              }
            });
          };
          instance.on('rendered', onRendered);
        }
        mark('set-option');
        chart.setOption(
          {
            ...current,
            animation: !reducedMotion,
            aria: { enabled: true, label: { description: label } },
          },
          { replaceMerge: ['series', ...(family === 'fighter' ? ['dataZoom'] : family === 'roster' ? ['visualMap'] : [])] },
        );
      } else if (renderedLabel !== label || renderedMotion !== reducedMotion)
        chart.setOption({
          animation: !reducedMotion,
          aria: { enabled: true, label: { description: label } },
        });
      renderedOption = current;
      renderedLabel = label;
      renderedMotion = reducedMotion;
    }
  });
</script>

<div class="chart" style:height={`${height}px`} bind:this={container} role="img" aria-label={label}>
  {#if !ready}<div class="chart-loading">
      {error ? 'Chart could not load. Reload to retry.' : 'Loading chart…'}
    </div>{/if}
</div>
