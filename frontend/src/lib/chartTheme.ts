export const colors = [
  '#1a1a1a',
  '#4a4a4a',
  '#737373',
  '#969696',
  '#b5b5b5',
  '#333333',
  '#616161',
];

export const fontFamily =
  '"JetBrains Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace';

export const baseOption = {
  backgroundColor: 'transparent',
  textStyle: {
    fontFamily,
    fontSize: 11,
    color: '#1a1a1a',
  },
  color: colors,
  grid: { left: 12, right: 16, top: 32, bottom: 12, containLabel: true },
  tooltip: {
    trigger: 'axis' as const,
    confine: true,
    renderMode: 'richText' as const,
    backgroundColor: '#1a1a1a',
    borderWidth: 0,
    textStyle: { color: '#f2f0e3', fontFamily, fontSize: 12 },
    padding: 12,
  },
  legend: {
    top: 0,
    textStyle: { color: '#1a1a1a', fontFamily, fontSize: 11 },
    icon: 'roundRect' as const,
    itemWidth: 12,
    itemHeight: 8,
  },
  animationDuration: 350,
  animationDurationUpdate: 250,
  animationEasing: 'cubicOut' as const,
  animationEasingUpdate: 'cubicOut' as const,
  aria: { enabled: true },
};

export const axis = {
  axisLine: { lineStyle: { color: '#1a1a1a', width: 1.5 } },
  axisTick: { show: true, lineStyle: { color: '#1a1a1a' } },
  axisLabel: { color: '#1a1a1a', fontFamily, fontSize: 11, hideOverlap: true },
  splitLine: { lineStyle: { color: '#d7d4c6', type: 'dashed' as const } },
  nameTextStyle: { color: '#3a3a3a', fontFamily, fontSize: 11, fontWeight: 600, align: 'left' as const },
};
