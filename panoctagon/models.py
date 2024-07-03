from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, TypeVar

from pydantic import BaseModel
from sqlmodel import Field, SQLModel

from panoctagon.enums import (
    Decision,
    FightResult,
    FightStyle,
    FightType,
    UFCDivisionNames,
)


class Division(SQLModel, table=True):
    promotion_uid: str = Field(primary_key=True, foreign_key="promotions.promotion_uid")
    division_uid: str = Field(primary_key=True)
    name: str
    weight_lbs: int


class UFCEvent(BaseModel):
    event_uid: str
    title: str
    event_date: str
    event_location: str


class ScrapingConfig(BaseModel):
    uid: str
    description: str
    base_url: str
    base_dir: Path
    path: Path


class FileContents(BaseModel):
    uid: str
    path: Path
    contents: str
    file_num: int
    n_files: int


class ScrapingWriteResult(BaseModel):
    config: Optional[ScrapingConfig]
    path: Optional[Path]
    success: bool
    attempts: int


class RunStats(BaseModel):
    start: float
    end: float
    n_ops: Optional[int]
    op_name: str
    successes: Optional[int]
    failures: Optional[int]


class ParsingIssue(BaseModel):
    issue: str
    uids: list[str]


class Fighter(SQLModel, table=True):
    fighter_uid: str = Field(primary_key=True)
    first_name: str
    last_name: str
    nickname: Optional[str]
    dob: Optional[str]
    place_of_birth: Optional[str]
    stance: Optional[str]
    style: Optional[str]
    height_inches: Optional[int]
    reach_inches: Optional[int]
    leg_reach_inches: Optional[int]


class ParsingResult(BaseModel):
    uid: str
    result: Optional[Any]
    issues: list[str]


class FighterParsingResult(ParsingResult):
    result: Fighter


class Fight(BaseModel):
    event_uid: str
    fight_uid: str
    fight_style: FightStyle
    fight_type: Optional[FightType]
    fight_division: Optional[UFCDivisionNames]
    fighter1_uid: str
    fighter2_uid: str
    fighter1_result: FightResult
    fighter2_result: FightResult
    decision: Optional[Decision]
    decision_round: Optional[int]
    decision_time_seconds: Optional[int]
    referee: Optional[str]


class RoundSigStats(BaseModel):
    fight_uid: str
    fighter_uid: str
    round_num: int
    sig_strikes_landed: int
    sig_strikes_attempted: int
    sig_strikes_head_landed: int
    sig_strikes_head_attempted: int
    sig_strikes_body_landed: int
    sig_strikes_body_attempted: int
    sig_strikes_leg_landed: int
    sig_strikes_leg_attempted: int
    sig_strikes_distance_landed: int
    sig_strikes_distance_attempted: int
    sig_strikes_clinch_landed: int
    sig_strikes_clinch_attempted: int
    sig_strikes_grounded_landed: int
    sig_strikes_grounded_attempted: int


class RoundTotalStats(BaseModel):
    fight_uid: str
    fighter_uid: str
    round_num: int
    knockdowns: int
    total_strikes_landed: int
    total_strikes_attempted: int
    takedowns_landed: int
    takedowns_attempted: int
    submissions_attempted: int
    reversals: int
    control_time_seconds: Optional[int]


class RoundStats(BaseModel):
    fight_uid: str
    fighter_uid: str
    round_num: int
    knockdowns: int
    total_strikes_landed: int
    total_strikes_attempted: int
    takedowns_landed: int
    takedowns_attempted: int
    submissions_attempted: int
    reversals: int
    control_time_seconds: Optional[int]
    fight_uid: str
    fighter_uid: str
    round_num: int
    sig_strikes_landed: int
    sig_strikes_attempted: int
    sig_strikes_head_landed: int
    sig_strikes_head_attempted: int
    sig_strikes_body_landed: int
    sig_strikes_body_attempted: int
    sig_strikes_leg_landed: int
    sig_strikes_leg_attempted: int
    sig_strikes_distance_landed: int
    sig_strikes_distance_attempted: int
    sig_strikes_clinch_landed: int
    sig_strikes_clinch_attempted: int
    sig_strikes_grounded_landed: int
    sig_strikes_grounded_attempted: int


class FightDetailsParsingResult(ParsingResult):
    result: Fight


class TotalStatsParsingResult(ParsingResult):
    result: list[RoundTotalStats]


class SigStatsParsingResult(ParsingResult):
    result: list[RoundSigStats]


class FightParsingResult(BaseModel):
    fight_uid: str
    fight_result: Optional[FightDetailsParsingResult]
    total_stats: Optional[TotalStatsParsingResult]
    sig_stats: Optional[SigStatsParsingResult]
    file_issues: list[str]


class Promotion(SQLModel, table=True):
    promotion_uid: str
    name: str
    founded_date: str


ParsingResultType = TypeVar("ParsingResultType", bound=ParsingResult)
BaseModelType = TypeVar("BaseModelType", bound=BaseModel)
