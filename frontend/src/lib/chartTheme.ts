export const colors = ['#253b32', '#9a9b8d', '#6b7c76', '#b4a58a', '#4b4f43', '#a59085', '#797e66'];
export const baseOption = {
  backgroundColor: 'transparent',
  textStyle: {
    fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace',
    fontSize: 11,
    color: '#69685f',
  },
  color: colors,
  grid: { left: 12, right: 16, top: 32, bottom: 12, containLabel: true },
  tooltip: {
    trigger: 'axis' as const,
    confine: true,
    renderMode: 'richText' as const,
    backgroundColor: '#1a1a1a',
    borderWidth: 0,
    textStyle: { color: '#f2f0e3', fontSize: 12 },
    padding: 12,
  },
  legend: {
    top: 0,
    textStyle: { color: '#69685f', fontSize: 11 },
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
  axisLine: { lineStyle: { color: '#d5d3c7' } },
  axisTick: { show: false },
  axisLabel: { color: '#69685f', fontSize: 10, hideOverlap: true },
  splitLine: { lineStyle: { color: '#e7e5da', type: 'dashed' as const } },
  nameTextStyle: { color: '#69685f', fontSize: 11, align: 'left' as const },
};
