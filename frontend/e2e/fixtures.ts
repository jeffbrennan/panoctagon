import type { Page } from '@playwright/test';
import type {
  FighterProfile,
  FighterSummary,
  Matchup,
  NetworkData,
  RosterAnalytics,
  UpcomingEvent,
} from '../src/lib/types';
export const alpha: FighterSummary = {
  fighter_uid: 'alpha',
  full_name: 'Alex Alpha',
  nickname: 'Ace',
  stance: 'Orthodox',
  division: 'MIDDLEWEIGHT',
  wins: 4,
  losses: 1,
  draws: 0,
};
export const bravo: FighterSummary = {
  fighter_uid: 'bravo',
  full_name: 'Blair Bravo',
  nickname: null,
  stance: 'Southpaw',
  division: 'MIDDLEWEIGHT',
  wins: 2,
  losses: 3,
  draws: 0,
};
export function profile(fighter: FighterSummary): FighterProfile {
  return {
    bio: {
      ...fighter,
      first_name: fighter.full_name.split(' ')[0],
      last_name: fighter.full_name.split(' ')[1],
      dob: '1990-01-01',
      place_of_birth: null,
      style: null,
      height_inches: 72,
      reach_inches: 74,
    },
    record: {
      wins: fighter.wins,
      losses: fighter.losses,
      draws: 0,
      no_contests: 0,
      total_fights: 5,
    },
    fights: Array.from({ length: 5 }, (_, i) => ({
      fight_uid: `fight${i}`,
      event_uid: `event${i}`,
      event_title: `UFC ${300 + i}`,
      event_date: `${2020 + i}-02-01`,
      opponent_uid: fighter.fighter_uid === 'alpha' ? 'bravo' : 'alpha',
      opponent_name: fighter.fighter_uid === 'alpha' ? bravo.full_name : alpha.full_name,
      result: i === 4 ? 'LOSS' : 'WIN',
      decision: i < 2 ? 'TKO' : 'UNANIMOUS_DECISION',
      decision_round: 3,
      fight_division: 'MIDDLEWEIGHT',
      closing_odds: i === 0 ? -150 : null,
      strikes_landed: 30 + i * 3,
      strikes_attempted: 60,
      strikes_absorbed: 20,
      sig_strikes_landed: 20,
      sig_strikes_attempted: 40,
      head: 10,
      body: 6,
      leg: 4,
      takedowns: 1,
      control_seconds: 50,
    })),
  };
}
const matchup: Matchup = {
  fight_uid: 'upcoming1',
  fight_division: 'MIDDLEWEIGHT',
  fight_type: 'REGULAR',
  fight_order: 1,
  fighter1_uid: 'alpha',
  fighter1_name: alpha.full_name,
  fighter1_record: '4-1-0',
  fighter1_reach: 74,
  fighter1_height: 72,
  fighter1_stance: 'Orthodox',
  fighter1_total_fights: 6,
  fighter1_closing_odds: -150,
  fighter2_uid: 'bravo',
  fighter2_name: bravo.full_name,
  fighter2_record: '2-3-0',
  fighter2_reach: 70,
  fighter2_height: 70,
  fighter2_stance: 'Southpaw',
  fighter2_total_fights: 5,
  fighter2_closing_odds: 125,
};
export const upcoming: UpcomingEvent[] = [
  {
    event_uid: 'next',
    event_title: 'UFC Fight Night: Alpha vs. Bravo',
    event_date: '2026-10-17',
    event_location: 'Edmonton, Canada',
    fights: [
      matchup,
      {
        ...matchup,
        fight_uid: 'upcoming2',
        fight_division: 'LIGHTWEIGHT',
        fighter1_name: 'Casey Charlie',
        fighter1_uid: 'charlie',
        fighter1_reach: null,
        fighter1_height: null,
      },
    ],
  },
  {
    event_uid: 'later',
    event_title: 'UFC 999',
    event_date: '2026-11-01',
    event_location: 'New York, USA',
    fights: [{ ...matchup, fight_uid: 'later1' }],
  },
];
export const network: NetworkData = {
  nodes: [
    { id: 'alpha', name: alpha.full_name, wins: 4, losses: 1, fights: 5, x: 0, y: 0 },
    { id: 'bravo', name: bravo.full_name, wins: 2, losses: 3, fights: 5, x: 100, y: 100 },
    { id: 'charlie', name: 'Casey Charlie', wins: 1, losses: 1, fights: 2, x: 200, y: -100 },
  ],
  links: [
    {
      source: 'alpha',
      target: 'bravo',
      fights: 2,
      source_wins: 1,
      target_wins: 1,
      draws: 0,
      no_contests: 0,
    },
    {
      source: 'bravo',
      target: 'charlie',
      fights: 1,
      source_wins: 1,
      target_wins: 0,
      draws: 0,
      no_contests: 0,
    },
  ],
};
export const roster: RosterAnalytics = {
  fighters: Array.from({ length: 45 }, (_, i) => ({
    fighter_uid: `fighter${i}`,
    fighter_name: i === 0 ? alpha.full_name : `Fighter ${String(i).padStart(2, '0')}`,
    total_fights: 50 - i,
    wins: Math.min(20, 50 - i),
    landed: 10 + i,
    absorbed: 15 + i / 2,
    opposition_strength: i * 10,
  })),
  targets: ['Head', 'Body', 'Leg'].flatMap((target) =>
    ['WIN', 'LOSS'].map((result) => ({ target, result, count: 50, values: [5, 15, 30, 45, 65] })),
  ),
  advantages: ['Age', 'Reach', 'Experience'].flatMap((metric) =>
    ['−5 to −2', '−2 to 0', '0 to +2', '+2 to +5'].map((bin, i) => ({
      metric,
      bin,
      count: 30,
      win_rate: 40 + i * 5,
    })),
  ),
};

export async function mockApi(page: Page) {
  const requests: string[] = [];
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api', '');
    requests.push(path + url.search);
    let data: unknown;
    if (path === '/metadata')
      data = {
        last_refresh: '2026-10-11',
        fighters: 2637,
        fights: 8512,
        first_year: 1993,
        last_year: 2026,
      };
    else if (path === '/upcoming') data = upcoming;
    else if (path === '/fighter')
      data = url.searchParams.get('name')?.includes('Blair') ? [bravo] : [alpha];
    else if (path === '/fighter/alpha/analytics') data = profile(alpha);
    else if (path === '/fighter/bravo/analytics') data = profile(bravo);
    else if (path === '/analytics/network') data = network;
    else if (path === '/analytics/roster') data = roster;
    else
      return route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: '{"detail":"Not found"}',
      });
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
  });
  return requests;
}
