from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


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
    avg_strikes_landed: Optional[float]
    avg_strikes_absorbed: Optional[float]
    head_strike_pct: Optional[float]
    body_strike_pct: Optional[float]
    leg_strike_pct: Optional[float]


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
