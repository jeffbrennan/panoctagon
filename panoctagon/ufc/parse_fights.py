import os
import re
import sqlite3

import polars as pl
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, fields, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import bs4

from panoctagon.common import (
    write_data_to_db,
    get_con,
    get_table_rows,
    FileContents,
    get_html_files,
)
from panoctagon.divisions import UFCDivisionNames


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


# fighter level outcome
class FightResult(str, Enum):
    WIN = "Win"
    LOSS = "Loss"
    NO_CONTEST = "No Contest"
    DQ = "Disqualification"
    DRAW = "Draw"


@dataclass
class Fight:
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


@dataclass
class RoundSigStats:
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


@dataclass
class RoundTotalStats:
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


@dataclass
class ParsingIssue:
    issue: str
    fight_uids: list[str]


def get_round_vals(
    round_data: bs4.Tag, actual_cols: list[str], expected_cols: list[str]
) -> list[dict[str, Any]]:
    vals = [
        val.text.strip()
        for val in round_data.findAll("p", class_="b-fight-details__table-text")
    ]
    f1_vals = [val for i, val in enumerate(vals) if i % 2 == 0]
    f2_vals = [val for i, val in enumerate(vals) if i % 2 == 1]

    f1_uid, f2_uid = [i["href"].split("/")[-1] for i in round_data.findAll("a")]
    if len(f1_vals) != len(actual_cols) or len(f2_vals) != len(actual_cols):
        raise ValueError(f"Expecting {len(expected_cols)} cols. Got {len(vals)} values")

    f1_sig_stats_raw = dict(zip(actual_cols, f1_vals))
    f2_sig_stats_raw = dict(zip(actual_cols, f2_vals))

    f1_sig_stats_raw["Fighter"] = f1_uid
    f2_sig_stats_raw["Fighter"] = f2_uid
    all_sig_stats_raw = [f1_sig_stats_raw, f2_sig_stats_raw]
    return all_sig_stats_raw


def parse_sig_stats(
    fight_html: bs4.BeautifulSoup, fight_uid: str
) -> list[RoundSigStats]:
    sig_stats_cols = [
        i.text.strip() for i in fight_html.findAll("table")[2].findAll("th")
    ]
    expected_cols = [
        "Fighter",
        "Sig. str",
        "Sig. str. %",
        "Head",
        "Body",
        "Leg",
        "Distance",
        "Clinch",
        "Ground",
    ]

    if sig_stats_cols != expected_cols:
        raise ValueError()

    sig_stats_per_round = get_table_rows(fight_html, 3)
    sig_stats = []
    for round_num, round_data in enumerate(sig_stats_per_round, 1):
        all_sig_stats_raw = get_round_vals(round_data, sig_stats_cols, expected_cols)

        for sig_stats_raw in all_sig_stats_raw:
            sig_strikes_landed, sig_strikes_attempted = get_split_stat(
                sig_stats_raw["Sig. str"], "of"
            )

            sig_strikes_head_landed, sig_strikes_head_attempted = get_split_stat(
                sig_stats_raw["Head"], "of"
            )
            sig_strikes_body_landed, sig_strikes_body_attempted = get_split_stat(
                sig_stats_raw["Body"], "of"
            )
            sig_strikes_leg_landed, sig_strikes_leg_attempted = get_split_stat(
                sig_stats_raw["Leg"], "of"
            )
            sig_strikes_distance_landed, sig_strikes_distance_attempted = (
                get_split_stat(sig_stats_raw["Distance"], "of")
            )
            sig_strikes_clinch_landed, sig_strikes_clinch_attempted = get_split_stat(
                sig_stats_raw["Clinch"], "of"
            )
            sig_strikes_ground_landed, sig_strikes_ground_attempted = get_split_stat(
                sig_stats_raw["Ground"], "of"
            )

            sig_stats.append(
                RoundSigStats(
                    fight_uid=fight_uid,
                    fighter_uid=sig_stats_raw["Fighter"],
                    round_num=round_num,
                    sig_strikes_landed=sig_strikes_landed,
                    sig_strikes_attempted=sig_strikes_attempted,
                    sig_strikes_head_landed=sig_strikes_head_landed,
                    sig_strikes_head_attempted=sig_strikes_head_attempted,
                    sig_strikes_body_landed=sig_strikes_body_landed,
                    sig_strikes_body_attempted=sig_strikes_body_attempted,
                    sig_strikes_leg_landed=sig_strikes_leg_landed,
                    sig_strikes_leg_attempted=sig_strikes_leg_attempted,
                    sig_strikes_distance_landed=sig_strikes_distance_landed,
                    sig_strikes_distance_attempted=sig_strikes_distance_attempted,
                    sig_strikes_clinch_landed=sig_strikes_clinch_landed,
                    sig_strikes_clinch_attempted=sig_strikes_clinch_attempted,
                    sig_strikes_grounded_landed=sig_strikes_ground_landed,
                    sig_strikes_grounded_attempted=sig_strikes_ground_attempted,
                )
            )

    return sig_stats


def get_split_stat(stat: str, sep: str) -> tuple[int, int]:
    "parses stat like `1 of 2` to a tuple containing `1` and `2`"
    val1, val2 = stat.split(f" {sep} ")
    return (int(val1), int(val2))


def parse_round_totals(
    fight_html: bs4.BeautifulSoup, fight_uid: str
) -> list[RoundTotalStats]:
    totals_cols = [i.text.strip() for i in fight_html.findAll("table")[0].findAll("th")]
    expected_cols = [
        "Fighter",
        "KD",
        "Sig. str.",
        "Sig. str. %",
        "Total str.",
        "Td",
        "Td %",
        "Sub. att",
        "Rev.",
        "Ctrl",
    ]
    if totals_cols != expected_cols:
        raise ValueError()

    totals_per_round = get_table_rows(fight_html, 1)
    totals = []
    for round_num, round_data in enumerate(totals_per_round, 1):
        all_totals_raw = get_round_vals(round_data, totals_cols, expected_cols)
        for totals_raw in all_totals_raw:
            total_strikes_landed, total_strikes_attempted = get_split_stat(
                totals_raw["Total str."], "of"
            )
            takedowns_landed, takedowns_attempted = get_split_stat(
                totals_raw["Td"], "of"
            )
            control_time = totals_raw["Ctrl"].split(":")
            if control_time[0] == "--":
                control_time_seconds = None
            else:
                control_time_seconds = (int(control_time[0]) * 60) + (
                    int(control_time[1])
                )
            totals.append(
                RoundTotalStats(
                    fight_uid=fight_uid,
                    fighter_uid=totals_raw["Fighter"],
                    round_num=round_num,
                    knockdowns=int(totals_raw["KD"]),
                    total_strikes_landed=total_strikes_landed,
                    total_strikes_attempted=total_strikes_attempted,
                    takedowns_landed=takedowns_landed,
                    takedowns_attempted=takedowns_attempted,
                    submissions_attempted=int(totals_raw["Sub. att"]),
                    reversals=int(totals_raw["Rev."]),
                    control_time_seconds=control_time_seconds,
                )
            )

    return totals


def combine_dataclasses(class1, class2):
    fields1 = {f.name: f.type for f in fields(class1)}
    fields2 = {f.name: f.type for f in fields(class2)}
    common_fields = set(fields1.keys()) & set(fields2.keys())

    combined_class_fields = []
    for field_name in common_fields:
        combined_class_fields.append((field_name, fields1[field_name]))

    combined_class_name = f"{class1.__name__}{class2.__name__}Combined"

    combined_class = type(
        combined_class_name,
        (),
        {name: field_type for name, field_type in combined_class_fields},
    )

    return combined_class


def get_event_uid(fight_html: bs4.BeautifulSoup) -> str:
    event_uid_results = [
        i for i in fight_html.findAll("a") if "event-details" in str(i)
    ]
    if len(event_uid_results) != 1:
        raise ValueError(f"Expected exactly one event, got {len(event_uid_results)}")

    event_uid = event_uid_results[0]["href"].split("/")[-1]
    return event_uid


@dataclass
class FightDetailsParsingResult:
    fight: Fight
    parsing_issues: list[str]


def parse_fight_details(
    fight_html: bs4.BeautifulSoup, event_uid: str, fight_uid: str
) -> FightDetailsParsingResult:
    tbl = get_table_rows(fight_html, 0)
    parsing_issues = []
    detail_headers = [
        i.text.strip() for i in fight_html.findAll("i", class_="b-fight-details__label")
    ][1:]
    detail_headers = [i.replace(":", "").strip() for i in detail_headers]

    decision_details = [
        re.sub("[ \t\n]+", " ", i.text).strip()
        for i in fight_html.findAll("i", class_="b-fight-details__text-item")
    ]
    decision_details_values = [i.split(": ")[-1] for i in decision_details]

    decision_round = None
    decision_time_seconds = None
    referee = None

    if "Round" in detail_headers:
        decision_round = int(decision_details_values[detail_headers.index("Round")])

    if "Time" in detail_headers:
        decision_round_time = decision_details_values[detail_headers.index("Time")]
        round_min, round_sec = decision_round_time.split(":")
        decision_time_seconds = (int(round_min) * 60) + int(round_sec)

    if "Referee" in detail_headers:
        referee = decision_details_values[detail_headers.index("Referee")]

    decision = fight_html.find("i", attrs={"style": "font-style: normal"})
    if decision is not None:
        decision = (
            decision.text.replace("KO/TKO", "TKO")
            .replace("TKO", "Technical Knockout")
            .replace("KO", "Knockout")
            .replace("DQ", "Disqualification")
            .strip()
        )

        if "Doctor's Stoppage" in decision:
            decision = "Doctor's Stoppage"
        try:
            decision = Decision(decision)
        except ValueError as e:
            parsing_issues.append(str(e))
            decision = None

    f1_uid, f2_uid = [i["href"].split("/")[-1] for i in tbl[0].findAll("a")]
    f1_result_raw, f2_result_raw = [
        i.findAll("i")[0].text.strip()
        for i in fight_html.findAll("div", "b-fight-details__person")
    ]

    fighter_results = []
    for result in [f1_result_raw, f2_result_raw]:
        result_clean = (
            result.replace("W", "Win")
            .replace("L", "Loss")
            .replace("D", "Draw")
            .replace("NC", "No Contest")
            .strip()
        )

        try:
            fighter_results.append(FightResult(result_clean))
        except ValueError as e:
            parsing_issues.append(str(e))
            fighter_results.append(None)

    f1_result, f2_result = fighter_results

    division_fight_type_raw = fight_html.find(
        "i", class_="b-fight-details__fight-title"
    )
    weight_division = None
    fight_type = None
    if division_fight_type_raw is not None:
        division_fight_type = (
            division_fight_type_raw.text.replace("UFC", "")
            .replace("Ultimate Fighter", "")
            .replace("Ultimate", "")
            .replace("Latin America", "")
            .replace("Australia vs. UK", "")
            .replace("TUF Nations Canada vs. Australia", "")
            .replace("Japan", "")
            .replace("Championship", "Title")
            .replace("Superfight", "Open Weight")
            .replace("Tournament Title", "Title")
            .replace("Tournament", "Open Weight")
            .replace("'", "")
            .strip()
        )

        division_fight_type = (
            re.sub("\\d", "", division_fight_type)
            .strip()
            .replace("Brazil", "")
            .replace("China", "")
            .replace("Interim", "")
        )
        division_fight_type_split = division_fight_type.split(" ")
        division_fight_type_split = [i for i in division_fight_type_split if i != ""]
        n_words = len(division_fight_type_split)

        if n_words == 4:
            weight_division = " ".join(division_fight_type_split[0:2])
            fight_type = " ".join(division_fight_type_split[2:4])
        elif n_words == 3:
            if "Title" in division_fight_type_split:
                weight_division = " ".join(division_fight_type_split[0:1])
                fight_type = " ".join(division_fight_type_split[1:3])
            elif division_fight_type_split[-1] == "Bout":
                weight_division = " ".join(division_fight_type_split[0:2])
                fight_type = " ".join(division_fight_type_split[2:3])
            else:
                parsing_issues.append(
                    f"unhandled 3 words division fight type parsing. {division_fight_type_split}"
                )

        elif n_words == 2:
            if division_fight_type == "Title Bout":
                weight_division = "Open Weight"
                fight_type = "Title Bout"
            else:
                weight_division, fight_type = division_fight_type.split(" ")
        else:
            parsing_issues.append(
                f"unhandled number of words  < 2 and > 4 {division_fight_type_split}"
            )

        try:
            fight_type = FightType(fight_type)
        except ValueError as e:
            parsing_issues.append(str(e))
            fight_type = None

        try:
            weight_division = UFCDivisionNames(weight_division)
        except ValueError as e:
            parsing_issues.append(str(e))
            weight_division = None

    fight = Fight(
        event_uid=event_uid,
        fight_uid=fight_uid,
        fight_style=FightStyle.MMA,
        fight_type=fight_type,
        fight_division=weight_division,
        fighter1_uid=f1_uid,
        fighter2_uid=f2_uid,
        fighter1_result=f1_result,
        fighter2_result=f2_result,
        decision=decision,
        decision_round=decision_round,
        decision_time_seconds=decision_time_seconds,
        referee=referee,
    )

    output = FightDetailsParsingResult(fight=fight, parsing_issues=parsing_issues)
    return output


@dataclass
class FightParsingResult:
    fight_uid: str
    fight_result: Optional[FightDetailsParsingResult]
    total_stats: Optional[list[RoundTotalStats]]
    sig_stats: Optional[list[RoundSigStats]]
    file_issues: list[str]


def check_file_issues(
    fight_contents: FileContents, fight_html: bs4.BeautifulSoup
) -> Optional[FightParsingResult]:
    file_error_indicators = [
        "Internal Server Error",
        "Round-by-round stats not currently available.",
    ]
    result = FightParsingResult(
        fight_uid=fight_contents.uid,
        fight_result=None,
        total_stats=None,
        sig_stats=None,
        file_issues=[],
    )
    fight_text = fight_html.text

    for error_indicator in file_error_indicators:
        if error_indicator in fight_text:
            result.file_issues = [error_indicator]
            print(f"[deleting {fight_contents.uid}] - {error_indicator}")
            fight_contents.path.unlink()
            return result

    fight_tables = fight_html.findAll("table")
    if len(fight_tables) != 4:
        result.file_issues = [f"unhandled number of tables: {len(fight_tables)}"]
    return None


def parse_fight(
    fight_contents: FileContents,
) -> FightParsingResult:
    file_issues = []
    if fight_contents.file_num % 100 == 0:
        print(f"[{fight_contents.file_num:05d} / {fight_contents.n_files-1:05d}]")

    fight_html = bs4.BeautifulSoup(fight_contents.contents, features="lxml")
    check_results = check_file_issues(fight_contents, fight_html)
    if check_results is not None:
        return check_results

    event_uid = get_event_uid(fight_html)
    fight_parsing_results = parse_fight_details(
        fight_html, event_uid, fight_contents.uid
    )
    total_stats = parse_round_totals(fight_html, fight_contents.uid)
    sig_stats = parse_sig_stats(fight_html, fight_contents.uid)

    return FightParsingResult(
        fight_uid=fight_contents.uid,
        fight_result=fight_parsing_results,
        total_stats=total_stats,
        sig_stats=sig_stats,
        file_issues=file_issues,
    )


def handle_parsing_issues(
    results: list[FightParsingResult], raise_error: bool
) -> list[FightParsingResult]:
    all_parsing_issues: list[ParsingIssue] = []
    for i, result in enumerate(results):
        if result.fight_result is None:
            continue

        parsing_issues = result.fight_result.parsing_issues
        if not parsing_issues:
            continue

        existing_issues = [i.issue for i in all_parsing_issues]
        for issue in parsing_issues:
            if issue in existing_issues:
                issue_index = existing_issues.index(issue)
                all_parsing_issues[issue_index].fight_uids += [result.fight_uid]
                continue

            all_parsing_issues.append(ParsingIssue(issue, [result.fight_uid]))

    n_parsing_issues = len(all_parsing_issues)
    clean_results = results
    if n_parsing_issues > 0:
        for i in all_parsing_issues:
            print(i)
        if raise_error:
            assert n_parsing_issues == 0
        problem_uids = [
            item
            for sublist in [i.fight_uids for i in all_parsing_issues]
            for item in sublist
        ]
        problem_uids_deduped = sorted(list(set(problem_uids)))
        print(f"removing {problem_uids} from insert")
        clean_results = [i for i in results if i.fight_uid not in problem_uids_deduped]
    return clean_results


def convert_dataclass_to_dataframe(dc) -> pl.DataFrame:
    dc_flat = [asdict(item) for sublist in dc for item in sublist]
    return pl.DataFrame(dc_flat)


def create_fight_tables(cur: sqlite3.Cursor) -> None:

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS
        ufc_fights(
            event_uid TEXT NOT NULL,
            fight_uid TEXT NOT NULL,
            fight_style TEXT NOT NULL,
            fight_type TEXT,
            fight_division TEXT,
            fighter1_uid TEXT NOT NULL,
            fighter2_uid TEXT NOT NULL,
            fighter1_result TEXT NOT NULL,
            fighter2_result TEXT NOT NULL,
            decision TEXT, 
            decision_round INTEGER,
            decision_time_seconds INTEGER,
            referee TEXT,
            PRIMARY KEY (event_uid, fight_uid),
            FOREIGN KEY (event_uid) references ufc_events(event_uid)
            ) STRICT;

    """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS
        ufc_fight_stats(
            fight_uid TEXT NOT NULL,
            fighter_uid TEXT NOT NULL,
            round_num INTEGER NOT NULL,
            knockdowns INTEGER,
            total_strikes_landed INTEGER,
            total_strikes_attempted INTEGER,
            takedowns_landed INTEGER,
            takedowns_attempted INTEGER,
            submissions_attempted INTEGER,
            reversals INTEGER,
            control_time_seconds INTEGER, 
            sig_strikes_landed INTEGER,
            sig_strikes_attempted INTEGER,
            sig_strikes_head_landed INTEGER,
            sig_strikes_head_attempted INTEGER,
            sig_strikes_body_landed INTEGER,
            sig_strikes_body_attempted INTEGER,
            sig_strikes_leg_landed INTEGER,
            sig_strikes_leg_attempted INTEGER,
            sig_strikes_distance_landed INTEGER,
            sig_strikes_distance_attempted INTEGER,
            sig_strikes_clinch_landed INTEGER,
            sig_strikes_clinch_attempted INTEGER,
            sig_strikes_grounded_landed INTEGER,
            sig_strikes_grounded_attempted INTEGER,
            PRIMARY KEY (fight_uid, fighter_uid, round_num),
            FOREIGN KEY (fight_uid) references ufc_fights(fight_uid)
            ) STRICT;

    """
    )


def write_fight_results_to_db(results: list[FightParsingResult]) -> None:
    con, cur = get_con()
    create_fight_tables(cur)

    sig_stats_flat = convert_dataclass_to_dataframe([i.sig_stats for i in results])
    total_stats_flat = convert_dataclass_to_dataframe(
        ([i.total_stats for i in results])
    )

    stats_combined = total_stats_flat.join(
        sig_stats_flat, on=["fight_uid", "fighter_uid", "round_num"]
    )

    stats_combined.head()
    stats_combined_tuples: list[tuple] = stats_combined.rows(named=False)
    headers = stats_combined.columns
    write_data_to_db(con, "ufc_fight_stats", stats_combined_tuples, headers)
    fights = [i.fight_result.fight for i in results if i.fight_result is not None]
    write_data_to_db(con, "ufc_fights", fights, None)


def main() -> None:
    cpu_count = os.cpu_count()
    if cpu_count is None:
        cpu_count = 4

    dir = Path(__file__).parents[2] / "data/raw/ufc/fights"
    fights = get_html_files(dir, "fight_uid", "ufc_fights")

    with ProcessPoolExecutor(max_workers=cpu_count - 1) as executor:
        results = list(executor.map(parse_fight, fights))

    clean_results = handle_parsing_issues(results, False)
    assert len(clean_results) > 0

    write_fight_results_to_db(clean_results)


if __name__ == "__main__":
    main()
