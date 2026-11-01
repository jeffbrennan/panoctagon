import type { EChartsOption } from 'echarts';
import type { CareerFight } from './types';
import { axis, baseOption, colors } from './chartTheme';
import { date, label, number, odds } from './format';

function category(fights: CareerFight[]) {
  return {
    ...axis,
    type: 'category' as const,
    data: fights.map((f) => date(f.event_date, true)),
    axisLabel: {
      ...axis.axisLabel,
      formatter: (value: string) => value.split(', ')[1],
      interval: 'auto' as const,
    },
  };
}
const valueAxis = (name: string) => ({
  ...axis,
  type: 'value' as const,
  name,
  nameLocation: 'end' as const,
});
const timeAxis = () => ({
  ...axis,
  type: 'time' as const,
  axisLabel: { ...axis.axisLabel, formatter: '{yyyy}', hideOverlap: true },
});
function fightTip(f: CareerFight): string {
  return `${date(f.event_date, true)}\n${f.event_title}\n${label(f.result)} vs ${f.opponent_name}\n${label(f.decision)}${f.closing_odds == null ? '' : ` · ${odds(f.closing_odds)}`}`;
}
function zoom(fights: CareerFight[]) {
  return fights.length > 20
    ? [
        {
          type: 'inside' as const,
          id: 'career-zoom-inside',
          filterMode: 'none' as const,
          zoomOnMouseWheel: false,
          moveOnMouseWheel: false,
        },
        {
          type: 'slider' as const,
          id: 'career-zoom-slider',
          height: 14,
          bottom: 0,
          borderColor: '#d5d3c7',
          fillerColor: '#d5d3c740',
        },
      ]
    : [];
}
export function timeline(fights: CareerFight[]): EChartsOption {
  let total = 0;
  return {
    ...baseOption,
    legend: { show: false },
    grid: { ...baseOption.grid, top: 28, bottom: fights.length > 20 ? 40 : 12 },
    tooltip: {
      ...baseOption.tooltip,
      trigger: 'item',
      formatter: (p: any) =>
        `${fightTip(fights[p.dataIndex])}\nStrikes absorbed: ${number(fights[p.dataIndex].strikes_absorbed)}\nRecorded career total: ${number(p.value[1])}`,
    },
    xAxis: timeAxis(),
    yAxis: valueAxis('Recorded strikes absorbed'),
    dataZoom: zoom(fights),
    series: [
      {
        name: 'Recorded career strikes absorbed',
        id: 'career-strikes',
        type: 'line',
        connectNulls: false,
        symbolSize: 9,
        symbol: 'circle',
        lineStyle: { color: '#4b4f43', width: 1.5 },
        areaStyle: { color: '#8d9b8b', opacity: 0.15 },
        data: fights.map((f) => {
          if (f.strikes_absorbed != null) total += f.strikes_absorbed;
          return {
            name: f.fight_uid,
            value: [f.event_date, f.strikes_absorbed == null ? null : total],
            itemStyle: {
              color: f.result === 'WIN' ? '#253b32' : f.result === 'LOSS' ? '#f2f0e3' : '#b4a58a',
              borderColor: '#253b32',
              borderWidth: 2,
            },
          };
        }),
      },
    ],
  };
}
export function outcomes(fights: CareerFight[]): EChartsOption {
  const methods = [...new Set(fights.map((f) => f.decision).filter((d): d is string => !!d))];
  return {
    ...baseOption,
    grid: { ...baseOption.grid, top: 64 },
    legend: { ...baseOption.legend, type: 'scroll', formatter: label },
    tooltip: {
      ...baseOption.tooltip,
      formatter: (params: any) =>
        `${params[0]?.axisValue}\n${params
          .filter((p: any) => p.value)
          .map((p: any) => `${label(p.seriesName)}: ${p.value}`)
          .join('\n')}`,
    },
    xAxis: { ...valueAxis('Fights'), nameLocation: 'middle', nameGap: 26 },
    yAxis: { ...axis, type: 'category', data: ['Losses', 'Wins'] },
    series: methods.map((method, i) => ({
      name: method,
      id: `outcome-${method}`,
      type: 'bar',
      stack: 'outcomes',
      barMaxWidth: 46,
      itemStyle: { color: colors[i % colors.length] },
      data: ['LOSS', 'WIN'].map(
        (result) => fights.filter((f) => f.result === result && f.decision === method).length,
      ),
    })),
  };
}
export function strikes(fights: CareerFight[]): EChartsOption {
  return {
    ...baseOption,
    grid: { ...baseOption.grid, top: 44, bottom: fights.length > 20 ? 40 : 12 },
    tooltip: {
      ...baseOption.tooltip,
      formatter: (params: any) => {
        const f = fights[params[0]?.dataIndex];
        return f
          ? `${fightTip(f)}\nLanded: ${number(f.strikes_landed)}\nAbsorbed: ${number(f.strikes_absorbed)}`
          : '';
      },
    },
    xAxis: category(fights),
    yAxis: valueAxis('Total strikes'),
    dataZoom: zoom(fights),
    series: [
      {
        name: 'Landed',
        id: 'strikes-landed',
        type: 'bar',
        data: fights.map((f) => f.strikes_landed),
        barMaxWidth: 20,
      },
      {
        name: 'Absorbed',
        id: 'strikes-absorbed',
        type: 'bar',
        data: fights.map((f) => f.strikes_absorbed),
        barMaxWidth: 20,
        itemStyle: { color: '#b8b7a9' },
      },
    ],
  };
}
export function accuracy(fights: CareerFight[]): EChartsOption {
  const eligible = fights.filter((f) => f.strikes_attempted != null && f.strikes_attempted > 0);
  return {
    ...baseOption,
    legend: { show: false },
    grid: { ...baseOption.grid, top: 24 },
    tooltip: {
      ...baseOption.tooltip,
      formatter: (params: any) => {
        const f = eligible[params[0]?.dataIndex];
        return f
          ? `${fightTip(f)}\nAccuracy: ${(((f.strikes_landed || 0) / f.strikes_attempted!) * 100).toFixed(1)}%\n${number(f.strikes_landed)} / ${number(f.strikes_attempted)} total strikes`
          : '';
      },
    },
    xAxis: timeAxis(),
    yAxis: { ...valueAxis('Accuracy (%)'), min: 0, max: 100 },
    series: [
      {
        name: 'Accuracy',
        id: 'strike-accuracy',
        type: 'line',
        smooth: 0.2,
        symbolSize: 6,
        data: eligible.map((f) => [
          f.event_date,
          ((f.strikes_landed || 0) / f.strikes_attempted!) * 100,
        ]),
        areaStyle: { opacity: 0.06 },
      },
    ],
  };
}
export function targets(fights: CareerFight[]): EChartsOption {
  return {
    ...baseOption,
    grid: { ...baseOption.grid, top: 44, bottom: fights.length > 20 ? 40 : 12 },
    tooltip: {
      ...baseOption.tooltip,
      formatter: (params: any) => {
        const f = fights[params[0]?.dataIndex];
        return f
          ? `${fightTip(f)}\nHead: ${number(f.head)} · Body: ${number(f.body)} · Leg: ${number(f.leg)}`
          : '';
      },
    },
    xAxis: category(fights),
    yAxis: valueAxis('Significant strikes'),
    dataZoom: zoom(fights),
    series: (['leg', 'body', 'head'] as const).map((key, i) => ({
      name: label(key),
      id: `target-${key}`,
      type: 'bar',
      stack: 'targets',
      barMaxWidth: 32,
      itemStyle: { color: ['#a6a88e', '#788476', '#2c4438'][i] },
      data: fights.map((f) => f[key]),
    })),
  };
}
