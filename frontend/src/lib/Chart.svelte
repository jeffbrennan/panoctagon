<script lang="ts">
  import { onMount } from 'svelte';
  import type { EChartsType } from 'echarts/core';
  import type { EChartsOption } from 'echarts';
  let {
    option,
    label,
    height = 320,
    onselect,
  }: {
    option: EChartsOption;
    label: string;
    height?: number;
    onselect?: (data: any) => void;
  } = $props();
  let container: HTMLDivElement;
  let chart = $state<EChartsType | null>(null);
  let error = $state(false);
  let ready = $state(false);
  let reducedMotion = false;
  let observer: ResizeObserver;
  let frame = 0;

  onMount(() => {
    let disposed = false;
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    reducedMotion = motion.matches;
    function updateMotion() {
      reducedMotion = motion.matches;
      chart?.setOption({ animation: !reducedMotion });
    }
    motion.addEventListener('change', updateMotion);
    const visibility = new IntersectionObserver(
      async (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        visibility.disconnect();
        try {
          const { init } = await import('./chart');
          if (disposed) return;
          chart = init(container, undefined, {
            renderer: 'canvas',
            devicePixelRatio: Math.min(window.devicePixelRatio || 1, 2),
          });
          chart.on('click', (params: any) => onselect?.(params.data));
          observer = new ResizeObserver(() => {
            cancelAnimationFrame(frame);
            frame = requestAnimationFrame(() => {
              if (container.clientWidth > 0) chart?.resize();
            });
          });
          observer.observe(container);
          ready = true;
        } catch {
          if (!disposed) error = true;
        }
      },
      { rootMargin: '100px' },
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
    if (chart)
      chart.setOption(
        {
          ...option,
          animation: !reducedMotion,
          aria: { enabled: true, label: { description: label } },
        },
        { replaceMerge: ['series', 'dataZoom', 'visualMap'], lazyUpdate: true },
      );
  });
</script>

<div class="chart" style:height={`${height}px`} bind:this={container} role="img" aria-label={label}>
  {#if !ready}<div class="chart-loading">
      {error ? 'Chart could not load. Reload to retry.' : 'Loading chart…'}
    </div>{/if}
</div>
