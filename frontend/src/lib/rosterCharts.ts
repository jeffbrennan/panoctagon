import type { EChartsOption } from 'echarts';
import type { Advantage, RosterPoint, TargetBox } from './types';
import { axis, baseOption } from './chartTheme';
import { number } from './format';

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
      min: 0,
      max: Math.max(...fighters.map((f) => f.opposition_strength), 1),
      dimension: 2,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemWidth: 10,
      itemHeight: 140,
      text: ['Stronger opposition', ''],
      textStyle: { fontSize: 10, color: '#69685f' },
      inRange: { color: ['#d2d4c9', '#7b8875', '#263f31'] },
      calculable: false,
    },
    series: [
      {
        type: 'scatter',
        name: 'Fighters',
        data: fighters.map((f) => ({
          value: [f.landed, f.absorbed, f.opposition_strength],
          fighter: f,
        })),
        symbolSize: (_value: any, params: any) =>
          Math.min(8 + params.data.fighter.total_fights * 0.65, 32),
        itemStyle: { borderColor: '#4b4f43', borderWidth: 1, opacity: 0.85 },
        emphasis: { scale: 1.3, itemStyle: { opacity: 1, borderWidth: 2 } },
        markLine: {
          symbol: 'none',
          silent: true,
          label: { show: false },
          lineStyle: { color: '#a6aa9a', type: 'dashed' },
          data: [[{ coord: [0, 0] }, { coord: [80, 80] }]],
        },
      },
    ],
  };
}
export function strikeTargets(targets: TargetBox[]): EChartsOption {
  return {
    ...baseOption,
    grid: { ...baseOption.grid, top: 44 },
    tooltip: {
      ...baseOption.tooltip,
      trigger: 'item',
      formatter: (p: any) => {
        const t = targets.find((t) => t.target === p.name && t.result === p.seriesName);
        return t
          ? `${t.target} · ${t.result}\n${t.count} fighter appearances\nMedian: ${t.values[2].toFixed(1)}%\nMiddle 50%: ${t.values[1].toFixed(1)}–${t.values[3].toFixed(1)}%`
          : '';
      },
    },
    xAxis: { ...axis, type: 'category', data: ['Head', 'Body', 'Leg'] },
    yAxis: {
      ...axis,
      type: 'value',
      min: 0,
      max: 100,
      name: 'Significant strikes (%)',
    },
    series: ['WIN', 'LOSS'].map((result) => ({
      name: result,
      type: 'boxplot',
      data: ['Head', 'Body', 'Leg'].map(
        (target) => targets.find((t) => t.target === target && t.result === result)?.values || [],
      ),
      itemStyle: {
        color: result === 'WIN' ? '#6b7c6d' : '#f2f0e3',
        borderColor: '#4b4f43',
        borderWidth: 1.5,
      },
    })),
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
      axisLabel: { ...axis.axisLabel, rotate: 25, fontSize: 9 },
    },
    yAxis: { ...axis, type: 'value', min: 20, max: 80, name: 'Win rate (%)' },
    series: [
      {
        type: 'line',
        name: 'Win rate',
        data: data.map((a) => a.win_rate),
        symbolSize: 8,
        smooth: 0.15,
        lineStyle: { width: 2 },
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { color: '#a4a697', type: 'dashed' },
          data: [{ yAxis: 50 }],
        },
      },
    ],
  };
}
