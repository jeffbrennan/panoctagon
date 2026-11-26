from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class FighterBio(BaseModel):
    fighter_uid: str
    first_name: str
    last_name: str
    full_name: str
    nickname: Optional[str]
    dob: Optional[str]
    place_of_birth: Optional[str]
    stance: Optional[str]
    style: Optional[str]
    height_inches: Optional[int]
    reach_inches: Optional[int]
    leg_reach_inches: Optional[int]


class FighterRecord(BaseModel):
    wins: int
    losses: int
    draws: int
    no_contests: int
    total_fights: int


class FightSummary(BaseModel):
    fight_uid: str
    event_title: str
    event_date: str
    fight_division: Optional[str]
    fight_type: Optional[str]
    opponent_name: str
    result: Optional[str]
    decision: Optional[str]
    decision_round: Optional[int]


class FighterDetail(BaseModel):
    bio: FighterBio
    record: FighterRecord
    recent_fights: list[FightSummary]


class FighterSearchResult(BaseModel):
    fighter_uid: str
    full_name: str
    nickname: Optional[str]
    stance: Optional[str]
    division: Optional[str]
    wins: int
    losses: int
    draws: int


class UpcomingMatchup(BaseModel):
    fight_uid: str
    event_uid: str
    event_title: str
    event_date: str
    event_location: str
    fight_division: Optional[str]
    fight_type: Optional[str]
    fight_order: Optional[int]
    fighter1_uid: str
    fighter1_name: str
    fighter1_record: str
    fighter1_reach: Optional[int]
    fighter1_height: Optional[int]
    fighter1_stance: Optional[str]
    fighter2_uid: str
    fighter2_name: str
    fighter2_record: str
    fighter2_reach: Optional[int]
    fighter2_height: Optional[int]
    fighter2_stance: Optional[str]
    fighter1_closing_odds: Optional[int] = None
    fighter2_closing_odds: Optional[int] = None
    fighter1_total_fights: int = 0
    fighter2_total_fights: int = 0


class UpcomingEvent(BaseModel):
    event_uid: str
    event_title: str
    event_date: str
    event_location: str
    fights: list[UpcomingMatchup]


class RankedFighter(BaseModel):
    rank: int
    fighter_uid: str
    full_name: str
    division: str
    wins: int
    losses: int
    draws: int
    win_rate: float
    total_fights: int
    ko_wins: int
    sub_wins: int
    dec_wins: int
    avg_sig_strikes: float
    strike_accuracy: float
    avg_takedowns: float
    total_knockdowns: int
    opp_win_rate: float


class FighterStats(BaseModel):
    avg_sig_strikes: Optional[float]
    strike_accuracy: Optional[float]
    avg_takedowns: Optional[float]
    total_knockdowns: int
    ko_wins: int
    sub_wins: int
    dec_wins: int
    avg_opp_win_rate: Optional[float]


class RosterFighter(BaseModel):
    fighter_uid: str
    full_name: str
    stance: Optional[str]
    division: Optional[str]
    wins: int
    losses: int
    draws: int
    win_rate: float
    total_fights: int
    ko_wins: int
    sub_wins: int
    dec_wins: int
    avg_sig_strikes: float
    strike_accuracy: float
    avg_takedowns: float
    total_knockdowns: int
    opp_win_rate: float


class EventSummary(BaseModel):
    event_uid: str
    title: str
    event_date: str
    event_location: str
    num_fights: int


class FightRoundStats(BaseModel):
    round_num: int
    knockdowns: Optional[int]
    total_strikes_landed: Optional[int]
    total_strikes_attempted: Optional[int]
    sig_strikes_landed: Optional[int]
    sig_strikes_attempted: Optional[int]
    takedowns_landed: Optional[int]
    takedowns_attempted: Optional[int]
    submissions_attempted: Optional[int]
    reversals: Optional[int]
    control_time_seconds: Optional[int]


class FightFighterStats(BaseModel):
    fighter_uid: str
    fighter_name: str
    result: Optional[str]
    rounds: list[FightRoundStats]


class FightDetail(BaseModel):
    fight_uid: str
    event_uid: str
    event_title: str
    event_date: str
    fight_division: Optional[str]
    fight_type: Optional[str]
    decision: Optional[str]
    decision_round: Optional[int]
    decision_time_seconds: Optional[int]
    referee: Optional[str]
    fighter1: FightFighterStats
    fighter2: FightFighterStats


class EventFight(BaseModel):
    fight_uid: str
    fight_division: Optional[str]
    fight_type: Optional[str]
    fight_order: Optional[int]
    fighter1_name: str
    fighter1_result: Optional[str]
    fighter2_name: str
    fighter2_result: Optional[str]
    decision: Optional[str]
    decision_round: Optional[int]


class EventDetail(BaseModel):
    event_uid: str
    title: str
    event_date: str
    event_location: str
    fights: list[EventFight]


class FighterFightSummary(BaseModel):
    fight_uid: str
    event_title: str
    event_date: str
    fight_division: Optional[str]
    opponent_name: str
    result: Optional[str]
    decision: Optional[str]
    decision_round: Optional[int]


class DashboardMetadata(BaseModel):
    revision: Optional[str] = None
    published_at: Optional[str] = None
    current_year: int
    last_refresh: Optional[str]
    fighters: int
    fights: int
    first_year: Optional[int]
    last_year: Optional[int]
    default_fighter_uid: Optional[str] = None


class CareerFight(BaseModel):
    fight_uid: str
    event_uid: str
    event_title: str
    event_date: str
    opponent_uid: str
    opponent_name: str
    result: str
    decision: Optional[str]
    decision_round: Optional[int]
    fight_division: Optional[str]
    closing_odds: Optional[int]
    strikes_landed: Optional[int]
    strikes_attempted: Optional[int]
    strikes_absorbed: Optional[int]
    sig_strikes_landed: Optional[int]
    sig_strikes_attempted: Optional[int]
    head: Optional[int]
    body: Optional[int]
    leg: Optional[int]
    takedowns: Optional[int]
    control_seconds: Optional[int]


class FighterAnalytics(BaseModel):
    bio: FighterBio
    record: FighterRecord
    fights: list[CareerFight]


class NetworkNode(BaseModel):
    id: str
    name: str
    wins: int
    losses: int
    fights: int
    x: float
    y: float


class NetworkLink(BaseModel):
    source: str
    target: str
    fights: int
    source_wins: int
    target_wins: int
    draws: int
    no_contests: int


class NetworkAnalytics(BaseModel):
    nodes: list[NetworkNode]
    links: list[NetworkLink]


class RosterPoint(BaseModel):
    fighter_uid: str
    fighter_name: str
    total_fights: int
    wins: int
    landed: float
    absorbed: float
    opposition_strength: int


class TargetOutlier(BaseModel):
    value: float
    fighter_uid: str
    fighter_name: str
    event_title: str
    event_date: str


class TargetBox(BaseModel):
    target: str
    result: str
    count: int
    values: tuple[float, float, float, float, float]
    outliers: list[TargetOutlier] = Field(default_factory=list)


class MatchupAdvantage(BaseModel):
    metric: str
    bin: str
    count: int
    win_rate: float


class RosterAnalytics(BaseModel):
    fighters: list[RosterPoint]
    targets: list[TargetBox]
    advantages: list[MatchupAdvantage]
