export type ChartFamily = 'fighter' | 'network' | 'roster';

const loaded = new Map<ChartFamily, Promise<typeof import('./chart')>>();

export function loadChart(family: ChartFamily) {
  let pending = loaded.get(family);
  if (!pending) {
    pending = Promise.all([
      import('./chart'),
      family === 'network'
        ? import('./echarts-network')
        : family === 'roster'
          ? import('./echarts-roster')
          : import('./echarts-fighter'),
    ]).then(
      ([runtime]) => runtime,
      (error) => {
        loaded.delete(family);
        throw error;
      },
    );
    loaded.set(family, pending);
  }
  return pending;
}

export function preloadChart(family: ChartFamily) {
  void loadChart(family).catch(() => {});
}
