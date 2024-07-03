from __future__ import annotations

from enum import Enum


class Symbols(Enum):
    DOWN_ARROW = "\u2193"
    DELETED = "\u2717"
    CHECK = "\u2714"


class FightStyle(str, Enum):
    MMA = "MMA"
    MUAY_THAI = "Muay Thai"
    BJJ = "Brazilian Jiu-Jitsu"


class FightType(str, Enum):
    BOUT = "Bout"
    TITLE = "Title Bout"


class Decision(str, Enum):
    KO = "Knockout"
    TKO = "Technical Knockout"
    DOC = "Doctor's Stoppage"
    SUB = "Submission"
    UNANIMOUS_DECISION = "Decision - Unanimous"
    SPLIT_DECISION = "Decision - Split"
    MAJORITY_DECISION = "Decision - Majority"
    DRAW = "Draw"
    NO_CONTEST = "No Contest"
    DQ = "Disqualification"
    OVERTURNED = "Overturned"
    COULD_NOT_CONTINUE = "Could Not Continue"
    OTHER = "Other"


class FightResult(str, Enum):
    WIN = "Win"
    LOSS = "Loss"
    NO_CONTEST = "No Contest"
    DQ = "Disqualification"
    DRAW = "Draw"


class Stance(str, Enum):
    ORTHODOX = "Orthodox"
    SOUTHPAW = "Southpaw"
    SWITCH = "Switch"
    SIDEWAYS = "Sideways"
    OPEN_STANCE = "Open Stance"


class UFCDivisionNames(str, Enum):
    STRAWWEIGHT = "Strawweight"
    WOMENS_STRAWWEIGHT = "Women's Strawweight"
    FLYWEIGHT = "Flyweight"
    WOMENS_FLYWEIGHT = "Women's Flyweight"
    BANTAMWEIGHT = "Bantamweight"
    WOMENS_BANTAMWEIGHT = "Women's Bantamweight"
    FEATHERWEIGHT = "Featherweight"
    WOMENS_FEATHERWEIGHT = "Women's Featherweight"
    LIGHTWEIGHT = "Lightweight"
    WELTERWEIGHT = "Welterweight"
    MIDDLEWEIGHT = "Middleweight"
    LIGHT_HEAVYWEIGHT = "Light Heavyweight"
    HEAVYWEIGHT = "Heavyweight"
    SUPER_HEAVYWEIGHT = "Super Heavyweight"
    CATCH_WEIGHT = "Catch Weight"
    OPEN_WEIGHT = "Open Weight"


class ONEDivisionNames(str, Enum):
    ATOMWEIGHT = "Atomweight"
    STRAWWEIGHT = "Strawweight"
    FLYWEIGHT = "Flyweight"
    BANTAMWEIGHT = "Bantamweight"
    FEATHERWEIGHT = "Featherweight"
    LIGHTWEIGHT = "Lightweight"
    WELTERWEIGHT = "Welterweight"
    MIDDLEWEIGHT = "Middleweight"
    LIGHT_HEAVYWEIGHT = "Light Heavyweight"
    HEAVYWEIGHT = "Heavyweight"
