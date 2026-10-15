import { describe, expect, it } from 'vitest';
import { timeline, accuracy } from './fighterCharts';
import type { CareerFight } from './types';
const fight = (id: string, value: Partial<CareerFight>): CareerFight => ({
  fight_uid: id,
  event_uid: 'event',
  event_title: 'UFC Test',
  event_date: '2026-01-01',
  opponent_uid: 'opponent',
  opponent_name: 'Opponent',
  result: 'WIN',
  decision: 'TKO',
  decision_round: 1,
  fight_division: 'MIDDLEWEIGHT',
  closing_odds: null,
  strikes_landed: null,
  strikes_attempted: null,
  strikes_absorbed: null,
  sig_strikes_landed: null,
  sig_strikes_attempted: null,
  head: null,
  body: null,
  leg: null,
  takedowns: null,
  control_seconds: null,
  ...value,
});
describe('fighter charts', () => {
  it('does not turn missing round data into a NaN career total', () => {
    const option = timeline([
      fight('first', { strikes_absorbed: 10 }),
      fight('missing', {}),
      fight('last', { strikes_absorbed: 20 }),
    ]);
    expect((option.series as any[])[0].data.map((p: any) => p.value[1])).toEqual([10, 10, 30]);
  });
  it('excludes unknown and zero-attempt accuracy rather than plotting false zeroes', () => {
    const option = accuracy([
      fight('missing', {}),
      fight('zero', { strikes_attempted: 0 }),
      fight('valid', { strikes_landed: 10, strikes_attempted: 20 }),
    ]);
    expect((option.series as any[])[0].data.map((p: any) => p[1])).toEqual([50]);
  });
});
