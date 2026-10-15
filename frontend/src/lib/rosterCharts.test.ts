import { expect, it } from 'vitest';
import { strikeTargets } from './rosterCharts';

it('keeps outlier fighter and event data attached to the plotted point', () => {
  const outlier = {
    value: 99,
    fighter_uid: 'alpha',
    fighter_name: 'Alex Alpha',
    event_title: 'UFC Test',
    event_date: '2026-01-01',
  };
  const chart = strikeTargets([
    { target: 'Head', result: 'WIN', count: 20, values: [20, 40, 60, 70, 90], outliers: [outlier] },
  ]);
  const point = (chart.series as any[])[1].data[0];
  expect(point.value).toEqual([0, 99]);
  expect(point.outlier).toEqual(outlier);
  const tooltip = (chart.tooltip as any).formatter({ data: point });
  expect(tooltip).toContain('Alex Alpha');
  expect(tooltip).toContain('UFC Test');
  expect(tooltip).toContain('Head strikes: 99.0%');
});
