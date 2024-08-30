import re
from typing import Any, Optional

import bs4
import polars as pl
from pydantic import TypeAdapter
from sqlmodel import col

from panoctagon.common import (
    create_header,
    delete_existing_records,
    get_table_rows,
    handle_parsing_issues,
    write_data_to_db,
)
from panoctagon.enums import (
    Decision,
    FightResult,
    FightStyle,
    FightType,
    UFCDivisionNames,
)
from panoctagon.models import (
    FightDetailsParsingResult,
    FightParsingResult,
    FileContents,
    RoundSigStats,
    RoundTotalStats,
    SigStatsParsingResult,
    TotalStatsParsingResult,
)
from panoctagon.tables import UFCFight, UFCFightStats


def get_split_stat(stat: str, sep: str) -> tuple[int, int]:
    """parses stat like `1 of 2` to a tuple containing `1` and `2`"""
    val1, val2 = stat.split(f" {sep} ")
    return int(val1), int(val2)


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
) -> SigStatsParsingResult:
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
    sig_stats: list[RoundSigStats] = []
    issues: list[str] = []
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

    return SigStatsParsingResult(uid=fight_uid, result=sig_stats, issues=issues)


def parse_round_totals(
    fight_html: bs4.BeautifulSoup, fight_uid: str
) -> TotalStatsParsingResult:
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
    totals: list[RoundTotalStats] = []
    issues: list[str] = []
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

    return TotalStatsParsingResult(uid=fight_uid, result=totals, issues=issues)


def get_event_uid(fight_html: bs4.BeautifulSoup) -> str:
    event_uid_results = [
        i for i in fight_html.findAll("a") if "event-details" in str(i)
    ]
    if len(event_uid_results) != 1:
        raise ValueError(f"Expected exactly one event, got {len(event_uid_results)}")

    event_uid = event_uid_results[0]["href"].split("/")[-1]
    return event_uid


def parse_fight_details(
    fight_html: bs4.BeautifulSoup, event_uid: str, fight_uid: str
) -> FightDetailsParsingResult:
    tbl = get_table_rows(fight_html)
    parsing_issues: list[str] = []

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

    fight_results: list[Optional[FightResult]] = []
    for result in [f1_result_raw, f2_result_raw]:
        result_clean = (
            result.replace("W", "Win")
            .replace("L", "Loss")
            .replace("D", "Draw")
            .replace("NC", "No Contest")
            .strip()
        )

        try:
            fight_results.append(FightResult(result_clean))
        except ValueError as e:
            parsing_issues.append(str(e))
            fight_results.append(None)

    f1_result, f2_result = fight_results

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
            .replace("Womens", "Women's")
            .replace("Road To", "")
            .replace("Road to", "")
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

    fight = UFCFight(
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

    return FightDetailsParsingResult(uid=fight_uid, result=fight, issues=parsing_issues)


def check_file_issues(
    fight_contents: FileContents, fight_html: bs4.BeautifulSoup
) -> Optional[FightParsingResult]:
    file_error_indicators = [
        "Round-by-round stats not currently available.",
    ]
    fight_text = fight_html.text

    for error_indicator in file_error_indicators:
        if error_indicator in fight_text:
            print(f"[deleting {fight_contents.uid}] - {error_indicator}")
            fight_contents.path.unlink()
            return FightParsingResult(
                fight_uid=fight_contents.uid,
                fight_result=None,
                total_stats=None,
                sig_stats=None,
                file_issues=[error_indicator],
            )

    fight_tables = fight_html.findAll("table")
    if len(fight_tables) != 4:
        return FightParsingResult(
            fight_uid=fight_contents.uid,
            fight_result=None,
            total_stats=None,
            sig_stats=None,
            file_issues=[f"unhandled number of tables: {len(fight_tables)}"],
        )
    return None


def parse_fight(
    fight_contents: FileContents,
) -> FightParsingResult:
    file_issues: list[str] = []
    if fight_contents.file_num % 100 == 0:
        title = f"[{fight_contents.file_num:05d} / {fight_contents.n_files-1:05d}]"
        print(create_header(80, title, False, "."))

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


def write_fight_results_to_db(
    results: list[FightParsingResult], force_run: bool
) -> None:
    tbl_name = "ufc_fights"
    print(create_header(80, tbl_name, True, spacer="-"))

    clean_fight_results = handle_parsing_issues(
        [i.fight_result for i in results if i.fight_result is not None], False
    )
    if len(clean_fight_results) == 0:
        print("no fights to write")
        return

    fights: list[UFCFight] = [i.result for i in clean_fight_results]

    if force_run:
        uids = [i.fight_uid for i in fights]
        delete_existing_records(UFCFight, col(UFCFight.fight_uid), uids)

    write_data_to_db(fights)


def write_stats_to_db(results: list[FightParsingResult]) -> None:
    tbl_name = "ufc_fight_stats"
    print(create_header(80, tbl_name, True, spacer="-"))

    clean_sig_stats = handle_parsing_issues(
        [i.sig_stats for i in results if i.sig_stats is not None], False
    )
    clean_total_stats = handle_parsing_issues(
        [i.total_stats for i in results if i.total_stats is not None], False
    )

    sig_stats_flat = pl.DataFrame(
        [item for sublist in [i.result for i in clean_sig_stats] for item in sublist]
    )
    total_stats_flat = pl.DataFrame(
        item for sublist in [i.result for i in clean_total_stats] for item in sublist
    )

    stats_combined_df = total_stats_flat.join(
        sig_stats_flat, on=["fight_uid", "fighter_uid", "round_num"]
    )

    uids = [i[0] for i in stats_combined_df.select("fight_uid").rows(named=False)]

    stats_combined_dict = stats_combined_df.rows(named=True)
    round_stats_adapter = TypeAdapter(list[UFCFightStats])
    stats_combined = round_stats_adapter.validate_python(stats_combined_dict)

    if len(stats_combined) == 0:
        print("no fights to write")
        return

    delete_existing_records(UFCFightStats, col(UFCFightStats.fight_uid), uids)

    write_data_to_db(stats_combined)
