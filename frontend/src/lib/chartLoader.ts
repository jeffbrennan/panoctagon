export type ChartFamily = 'fighter' | 'network' | 'roster';

export async function loadChart(family: ChartFamily) {
  const [runtime] = await Promise.all([
    import('./chart'),
    family === 'network'
      ? import('./echarts-network')
      : family === 'roster'
        ? import('./echarts-roster')
        : import('./echarts-fighter'),
  ]);
  return runtime;
}
