from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from panoctagon.enums import (
    Decision,
    FightResult,
    FightStyle,
    FightType,
    UFCDivisionNames,
)


class Promotions(SQLModel, table=True):
    promotion_uid: str = Field(primary_key=True, unique=True)
    name: str
    founded_date: str


class Divisions(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("promotion_uid", "name", name="divisions_pk"),)
    promotion_uid: str = Field(primary_key=True, foreign_key="promotions.promotion_uid")
    division_uid: str = Field(primary_key=True)
    name: str
    weight_lbs: int
    updated_ts: datetime.datetime = datetime.datetime.now(datetime.UTC)


class UFCEvent(SQLModel, table=True):
    __tablename__ = "ufc_events"  # pyright: ignore [reportAssignmentType]

    event_uid: str = Field(primary_key=True)
    title: str
    event_date: str
    event_location: str
    downloaded_ts: Optional[str] = None


class UFCFighter(SQLModel, table=True):
    __tablename__ = "ufc_fighters"  # pyright: ignore [reportAssignmentType]
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
    has_headshot: bool = False
    downloaded_ts: Optional[str] = None
    bio_downloaded_ts: Optional[str] = None


class UFCFight(SQLModel, table=True):
    __tablename__ = "ufc_fights"  # pyright: ignore [reportAssignmentType]
    __table_args__ = (UniqueConstraint("event_uid", "fight_uid", name="fight_pk"),)

    event_uid: str = Field(primary_key=True, foreign_key="ufc_events.event_uid")
    fight_uid: str = Field(primary_key=True)
    fight_style: FightStyle
    fight_type: Optional[FightType] = None
    fight_division: Optional[UFCDivisionNames] = None
    fighter1_uid: str = Field(foreign_key="ufc_fighters.fighter_uid")
    fighter2_uid: str = Field(foreign_key="ufc_fighters.fighter_uid")
    fighter1_result: Optional[FightResult] = None
    fighter2_result: Optional[FightResult] = None
    decision: Optional[Decision] = None
    decision_round: Optional[int] = None
    decision_time_seconds: Optional[int] = None
    referee: Optional[str] = None


class UFCFightStats(SQLModel, table=True):
    __tablename__ = "ufc_fight_stats"  # pyright: ignore
    fight_uid: str = Field(primary_key=True, foreign_key="ufc_fights.fight_uid")
    fighter_uid: str = Field(primary_key=True, foreign_key="ufc_fighters.fighter_uid")
    round_num: int = Field(primary_key=True)
    knockdowns: Optional[int] = None
    total_strikes_landed: Optional[int] = None
    total_strikes_attempted: Optional[int] = None
    takedowns_landed: Optional[int] = None
    takedowns_attempted: Optional[int] = None
    submissions_attempted: Optional[int] = None
    reversals: Optional[int] = None
    control_time_seconds: Optional[int] = None
    sig_strikes_landed: Optional[int] = None
    sig_strikes_attempted: Optional[int] = None
    sig_strikes_head_landed: Optional[int] = None
    sig_strikes_head_attempted: Optional[int] = None
    sig_strikes_body_landed: Optional[int] = None
    sig_strikes_body_attempted: Optional[int] = None
    sig_strikes_leg_landed: Optional[int] = None
    sig_strikes_leg_attempted: Optional[int] = None
    sig_strikes_distance_landed: Optional[int] = None
    sig_strikes_distance_attempted: Optional[int] = None
    sig_strikes_clinch_landed: Optional[int] = None
    sig_strikes_clinch_attempted: Optional[int] = None
    sig_strikes_grounded_landed: Optional[int] = None
    sig_strikes_grounded_attempted: Optional[int] = None


class TempBulkDeleteTest(SQLModel, table=True):
    uid: str = Field(primary_key=True)
    another_col: str
