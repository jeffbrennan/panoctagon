export type View = 'upcoming' | 'fighters' | 'network' | 'roster';
export interface FighterSummary {
  fighter_uid: string;
  full_name: string;
  nickname: string | null;
  stance: string | null;
  division: string | null;
  wins: number;
  losses: number;
  draws: number;
}
export interface Matchup {
  fight_uid: string;
  fight_division: string | null;
  fight_type: string | null;
  fight_order: number | null;
  fighter1_uid: string;
  fighter1_name: string;
  fighter1_record: string;
  fighter1_reach: number | null;
  fighter1_height: number | null;
  fighter1_stance: string | null;
  fighter2_uid: string;
  fighter2_name: string;
  fighter2_record: string;
  fighter2_reach: number | null;
  fighter2_height: number | null;
  fighter2_stance: string | null;
  fighter1_closing_odds?: number | null;
  fighter2_closing_odds?: number | null;
  fighter1_total_fights?: number;
  fighter2_total_fights?: number;
}
export interface UpcomingEvent {
  event_uid: string;
  event_title: string;
  event_date: string;
  event_location: string;
  fights: Matchup[];
}
export interface Metadata {
  last_refresh: string | null;
  fighters: number;
  fights: number;
  first_year: number;
  last_year: number;
}
export interface FighterBio {
  fighter_uid: string;
  full_name: string;
  first_name: string;
  last_name: string;
  nickname: string | null;
  dob: string | null;
  place_of_birth: string | null;
  stance: string | null;
  style: string | null;
  height_inches: number | null;
  reach_inches: number | null;
}
export interface CareerFight {
  fight_uid: string;
  event_uid: string;
  event_title: string;
  event_date: string;
  opponent_uid: string;
  opponent_name: string;
  result: string;
  decision: string | null;
  decision_round: number | null;
  fight_division: string | null;
  closing_odds: number | null;
  strikes_landed: number | null;
  strikes_attempted: number | null;
  strikes_absorbed: number | null;
  sig_strikes_landed: number | null;
  sig_strikes_attempted: number | null;
  head: number | null;
  body: number | null;
  leg: number | null;
  takedowns: number | null;
  control_seconds: number | null;
}
export interface FighterProfile {
  bio: FighterBio;
  record: {
    wins: number;
    losses: number;
    draws: number;
    no_contests: number;
    total_fights: number;
  };
  fights: CareerFight[];
}
export interface NetworkData {
  nodes: {
    id: string;
    name: string;
    wins: number;
    losses: number;
    fights: number;
    x: number;
    y: number;
  }[];
  links: {
    source: string;
    target: string;
    fights: number;
    source_wins: number;
    target_wins: number;
    draws: number;
    no_contests: number;
  }[];
}
export interface RosterPoint {
  fighter_uid: string;
  fighter_name: string;
  total_fights: number;
  wins: number;
  landed: number;
  absorbed: number;
  opposition_strength: number;
}
export interface TargetOutlier {
  value: number;
  fighter_uid: string;
  fighter_name: string;
  event_title: string;
  event_date: string;
}
export interface TargetBox {
  target: string;
  result: string;
  count: number;
  values: number[];
  outliers?: TargetOutlier[];
}
export interface Advantage {
  metric: string;
  bin: string;
  count: number;
  win_rate: number;
}
export interface RosterAnalytics {
  fighters: RosterPoint[];
  targets: TargetBox[];
  advantages: Advantage[];
}
