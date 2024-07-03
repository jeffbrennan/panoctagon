from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, TypeVar

from pydantic import BaseModel
from sqlmodel import SQLModel

from panoctagon.tables import UFCFight, UFCFighter


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


class ParsingResult(BaseModel):
    uid: str
    result: Optional[Any]
    issues: list[str]


class FighterParsingResult(ParsingResult):
    result: UFCFighter


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


class FightDetailsParsingResult(ParsingResult):
    result: UFCFight


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


ParsingResultType = TypeVar("ParsingResultType", bound=ParsingResult)
SQLModelType = TypeVar("SQLModelType", bound=SQLModel)
