import type { EChartsOption } from 'echarts';
import type { Advantage, RosterPoint, TargetBox } from './types';
import { axis, baseOption, fontFamily } from './chartTheme';
import { date, number } from './format';

export function strikingType(fighters: RosterPoint[]): EChartsOption {
  return {
    ...baseOption,
    legend: { show: false },
    grid: { left: 16, right: 24, bottom: 68, top: 24, containLabel: true },
    tooltip: {
      ...baseOption.tooltip,
      trigger: 'item',
      formatter: (p: any) => {
        const f = p.data.fighter;
        return `${f.fighter_name}\n${f.total_fights} fights · ${Math.round((f.wins / f.total_fights) * 100)}% wins\nMedian strikes landed: ${number(f.landed, 1)}\nMedian strikes absorbed: ${number(f.absorbed, 1)}\nOpposition strength: ${f.opposition_strength}\nClick to view fighter`;
      },
    },
    xAxis: {
      ...axis,
      type: 'value',
      name: 'Median strikes landed / round',
      nameLocation: 'middle',
      nameGap: 28,
    },
    yAxis: { ...axis, type: 'value', name: 'Median strikes absorbed / round' },
    visualMap: {
      id: 'opposition-strength',
      min: 0,
      max: Math.max(...fighters.map((f) => f.opposition_strength), 1),
      dimension: 2,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemWidth: 10,
      itemHeight: 140,
      text: ['Stronger opposition', ''],
      textStyle: { fontSize: 10, fontFamily, color: '#1a1a1a' },
      inRange: { color: ['#c8c8c8', '#7a7a7a', '#1a1a1a'] },
      calculable: false,
    },
    series: [
      {
        type: 'scatter',
        name: 'Fighters',
        id: 'fighter-striking',
        progressive: 200,
        progressiveThreshold: 500,
        progressiveChunkMode: 'mod',
        animationThreshold: 400,
        data: fighters.map((f) => ({
          value: [f.landed, f.absorbed, f.opposition_strength],
          fighter: f,
        })),
        symbolSize: (_value: any, params: any) =>
          Math.min(8 + params.data.fighter.total_fights * 0.65, 32),
        itemStyle: { borderColor: '#1a1a1a', borderWidth: 1, opacity: 0.85 },
        emphasis: { scale: 1.3, itemStyle: { opacity: 1, borderWidth: 2, borderColor: '#d20a0a' } },
        markLine: {
          symbol: 'none',
          silent: true,
          label: { show: false },
          lineStyle: { color: '#7a7a7a', type: 'dashed' },
          data: [[{ coord: [0, 0] }, { coord: [80, 80] }]],
        },
      },
    ],
  };
}
export function strikeTargets(targets: TargetBox[]): EChartsOption {
  const boxes = ['Head', 'Body', 'Leg'].flatMap((target) =>
    ['WIN', 'LOSS'].map(
      (result) =>
        targets.find((t) => t.target === target && t.result === result) || {
          target,
          result,
          count: 0,
          values: [],
          outliers: [],
        },
    ),
  );
  return {
    ...baseOption,
    legend: { show: false },
    grid: { ...baseOption.grid, top: 28 },
    tooltip: {
      ...baseOption.tooltip,
      trigger: 'item',
      formatter: (p: any) => {
        if (p.data.outlier) {
          const point = p.data.outlier;
          return `${point.fighter_name}\n${point.event_title} · ${date(point.event_date, true)}\n${p.data.target} strikes: ${point.value.toFixed(1)}% · ${p.data.result}\nClick to view fighter`;
        }
        const t = p.data.distribution;
        return t
          ? `${t.target} · ${t.result}\n${t.count} fighter appearances\nMedian: ${t.values[2].toFixed(1)}%\nMiddle 50%: ${t.values[1].toFixed(1)}–${t.values[3].toFixed(1)}%`
          : '';
      },
    },
    xAxis: {
      ...axis,
      type: 'category',
      data: boxes.map((t) => `${t.target}\n${t.result === 'WIN' ? 'Win' : 'Loss'}`),
      axisLabel: { ...axis.axisLabel, interval: 0, fontSize: 11, lineHeight: 16 },
    },
    yAxis: { ...axis, type: 'value', min: 0, max: 100, name: 'Significant strikes (%)' },
    series: [
      {
        name: 'Target distribution',
        id: 'target-distribution',
        type: 'boxplot',
        boxWidth: ['35%', '60%'],
        data: boxes.map((t) => ({
          value: t.values,
          distribution: t,
          itemStyle: {
            color: t.result === 'WIN' ? '#5c5c5c' : '#f2f0e3',
            borderColor: '#1a1a1a',
            borderWidth: 1.5,
          },
        })),
      },
      {
        name: 'Outliers',
        id: 'target-outliers',
        type: 'scatter',
        symbolSize: 5,
        itemStyle: { color: '#1a1a1a', opacity: 0.65 },
        data: boxes.flatMap((t, index) =>
          (t.outliers || []).map((outlier) => ({
            value: [index, outlier.value],
            outlier,
            target: t.target,
            result: t.result,
          })),
        ),
      },
    ],
  };
}
export function discrepancy(advantages: Advantage[], metric: string): EChartsOption {
  const data = advantages.filter((a) => a.metric === metric);
  const units = {
    Age: 'years older',
    Reach: 'inches longer',
    Experience: 'more UFC fights',
  }[metric];
  return {
    ...baseOption,
    legend: { show: false },
    grid: { left: 12, right: 12, top: 28, bottom: 32, containLabel: true },
    tooltip: {
      ...baseOption.tooltip,
      formatter: (params: any) => {
        const a = data[params[0]?.dataIndex];
        return a
          ? `${metric}: ${a.bin}\nWin rate: ${a.win_rate.toFixed(1)}%\n${a.count} fighter appearances`
          : '';
      },
    },
    xAxis: {
      ...axis,
      type: 'category',
      data: data.map((a) => a.bin),
      name: units,
      nameLocation: 'middle',
      nameGap: 30,
      axisLabel: { ...axis.axisLabel, rotate: 25, fontSize: 11 },
    },
    yAxis: { ...axis, type: 'value', min: 0, max: 100, name: 'Win rate (%)' },
    series: [
      {
        type: 'line',
        name: 'Win rate',
        id: 'matchup-advantage',
        data: data.map((a) => a.win_rate),
        symbolSize: 8,
        lineStyle: { color: '#1a1a1a', width: 2 },
        itemStyle: { color: '#1a1a1a' },
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { color: '#7a7a7a', type: 'dashed' },
          data: [{ yAxis: 50 }],
        },
      },
    ],
  };
}
