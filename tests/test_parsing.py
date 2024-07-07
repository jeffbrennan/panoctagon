from pathlib import Path

import bs4
import pytest
from sqlmodel import col

from panoctagon.common import (
    get_html_files,
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
    RoundSigStats,
    RoundTotalStats,
    SigStatsParsingResult,
    TotalStatsParsingResult,
)
from panoctagon.tables import UFCFight
from panoctagon.ufc.parse_fights import (
    get_event_uid,
    parse_fight_details,
    parse_round_totals,
    parse_sig_stats,
)


def _get_fight_html(fight_dir, uid: str) -> bs4.BeautifulSoup:
    fight_contents = get_html_files(
        fight_dir,
        col(UFCFight.fight_uid),
        force_run=True,
        uid=uid,
    )
    assert len(fight_contents) == 1
    return bs4.BeautifulSoup(fight_contents[0].contents, features="lxml")


def _test_parse_fight_details(
    fight_html, event_uid, fight_uid, expected: FightDetailsParsingResult
) -> None:
    actual = parse_fight_details(fight_html, event_uid, fight_uid)
    result_matches = actual == expected
    if not result_matches:
        print(actual.result)
        print("-----")
        print(expected.result)
        assert result_matches


def _test_total_stats(fight_html, fight_uid, expected: TotalStatsParsingResult) -> None:
    actual = parse_round_totals(fight_html, fight_uid)
    result_matches = actual == expected
    if not result_matches:
        print(actual.result)
        print("-----")
        print(expected.result)
        assert result_matches


def _test_sig_stats(fight_html, fight_uid, expected: SigStatsParsingResult) -> None:
    actual = parse_sig_stats(fight_html, fight_uid)
    result_matches = actual == expected
    if not result_matches:
        print(actual.result)
        print("-----")
        print(expected.result)
        assert result_matches


def _run_test_parse_details(
    fight_dir: Path, expected_results: list[FightDetailsParsingResult]
) -> None:
    for expected in expected_results:
        fight_html = _get_fight_html(fight_dir, expected.uid)
        event_uid = get_event_uid(fight_html)
        _test_parse_fight_details(
            fight_html, event_uid, expected.uid, expected=expected
        )


def _run_total_stats(
    fight_dir: Path, expected_results: list[TotalStatsParsingResult]
) -> None:
    for expected in expected_results:
        fight_html = _get_fight_html(fight_dir, expected.uid)
        _test_total_stats(fight_html, expected.uid, expected=expected)


def _run_sig_stats(
    fight_dir: Path, expected_results: list[SigStatsParsingResult]
) -> None:
    for expected in expected_results:
        fight_html = _get_fight_html(fight_dir, expected.uid)
        _test_sig_stats(fight_html, expected.uid, expected=expected)


def test_road_to():
    # uid='98094a500529d442'
    raise NotImplementedError()


def test_no_valid_apostrophe_removal():
    # uid='1685eecc7ef37fb5'
    raise NotImplementedError()


def test_superfight_details(fight_dir):
    expected_results = [
        FightDetailsParsingResult(
            uid="6a060498e60756af",
            result=UFCFight(
                event_uid="a390eb8a9b2df298",
                fight_uid="6a060498e60756af",
                fight_style=FightStyle.MMA,
                fight_type=FightType.TITLE,
                fight_division=UFCDivisionNames.OPEN_WEIGHT,
                fighter1_uid="c670aa48827d6be6",
                fighter2_uid="63b65af1c5cb02cb",
                fighter1_result=FightResult.WIN,
                fighter2_result=FightResult.LOSS,
                decision=Decision.SPLIT_DECISION,
                decision_round=3,
                decision_time_seconds=180,
                referee="John McCarthy",
            ),
            issues=[],
        )
    ]
    _run_test_parse_details(fight_dir, expected_results)


def test_superfight_total_stats(fight_dir):
    expected_results = [
        TotalStatsParsingResult(
            uid="6a060498e60756af",
            issues=[],
            result=[
                RoundTotalStats(
                    fight_uid="6a060498e60756af",
                    fighter_uid="c670aa48827d6be6",
                    round_num=1,
                    knockdowns=0,
                    total_strikes_landed=29,
                    total_strikes_attempted=74,
                    takedowns_landed=0,
                    takedowns_attempted=2,
                    submissions_attempted=0,
                    reversals=1,
                    control_time_seconds=None,
                ),
                RoundTotalStats(
                    fight_uid="6a060498e60756af",
                    fighter_uid="63b65af1c5cb02cb",
                    round_num=1,
                    knockdowns=0,
                    total_strikes_landed=55,
                    total_strikes_attempted=105,
                    takedowns_landed=0,
                    takedowns_attempted=0,
                    submissions_attempted=0,
                    reversals=0,
                    control_time_seconds=None,
                ),
                RoundTotalStats(
                    fight_uid="6a060498e60756af",
                    fighter_uid="c670aa48827d6be6",
                    round_num=2,
                    knockdowns=0,
                    total_strikes_landed=0,
                    total_strikes_attempted=4,
                    takedowns_landed=0,
                    takedowns_attempted=0,
                    submissions_attempted=0,
                    reversals=0,
                    control_time_seconds=None,
                ),
                RoundTotalStats(
                    fight_uid="6a060498e60756af",
                    fighter_uid="63b65af1c5cb02cb",
                    round_num=2,
                    knockdowns=0,
                    total_strikes_landed=0,
                    total_strikes_attempted=2,
                    takedowns_landed=0,
                    takedowns_attempted=0,
                    submissions_attempted=0,
                    reversals=0,
                    control_time_seconds=None,
                ),
                RoundTotalStats(
                    fight_uid="6a060498e60756af",
                    fighter_uid="c670aa48827d6be6",
                    round_num=3,
                    knockdowns=0,
                    total_strikes_landed=3,
                    total_strikes_attempted=16,
                    takedowns_landed=0,
                    takedowns_attempted=0,
                    submissions_attempted=0,
                    reversals=0,
                    control_time_seconds=None,
                ),
                RoundTotalStats(
                    fight_uid="6a060498e60756af",
                    fighter_uid="63b65af1c5cb02cb",
                    round_num=3,
                    knockdowns=0,
                    total_strikes_landed=4,
                    total_strikes_attempted=15,
                    takedowns_landed=0,
                    takedowns_attempted=1,
                    submissions_attempted=0,
                    reversals=0,
                    control_time_seconds=None,
                ),
            ],
        ),
    ]
    _run_total_stats(fight_dir, expected_results)


def test_superfight_sig_stats(fight_dir):
    expected_results: list[SigStatsParsingResult] = [
        SigStatsParsingResult(
            result=[
                RoundSigStats(
                    fight_uid="6a060498e60756af",
                    fighter_uid="c670aa48827d6be6",
                    round_num=1,
                    sig_strikes_landed=13,
                    sig_strikes_attempted=55,
                    sig_strikes_head_landed=11,
                    sig_strikes_head_attempted=53,
                    sig_strikes_body_landed=0,
                    sig_strikes_body_attempted=0,
                    sig_strikes_leg_landed=2,
                    sig_strikes_leg_attempted=2,
                    sig_strikes_distance_landed=7,
                    sig_strikes_distance_attempted=46,
                    sig_strikes_clinch_landed=0,
                    sig_strikes_clinch_attempted=0,
                    sig_strikes_grounded_landed=6,
                    sig_strikes_grounded_attempted=9,
                ),
                RoundSigStats(
                    fight_uid="6a060498e60756af",
                    fighter_uid="63b65af1c5cb02cb",
                    round_num=1,
                    sig_strikes_landed=14,
                    sig_strikes_attempted=64,
                    sig_strikes_head_landed=6,
                    sig_strikes_head_attempted=55,
                    sig_strikes_body_landed=8,
                    sig_strikes_body_attempted=9,
                    sig_strikes_leg_landed=0,
                    sig_strikes_leg_attempted=0,
                    sig_strikes_distance_landed=5,
                    sig_strikes_distance_attempted=55,
                    sig_strikes_clinch_landed=0,
                    sig_strikes_clinch_attempted=0,
                    sig_strikes_grounded_landed=9,
                    sig_strikes_grounded_attempted=9,
                ),
                RoundSigStats(
                    fight_uid="6a060498e60756af",
                    fighter_uid="c670aa48827d6be6",
                    round_num=2,
                    sig_strikes_landed=0,
                    sig_strikes_attempted=4,
                    sig_strikes_head_landed=0,
                    sig_strikes_head_attempted=4,
                    sig_strikes_body_landed=0,
                    sig_strikes_body_attempted=0,
                    sig_strikes_leg_landed=0,
                    sig_strikes_leg_attempted=0,
                    sig_strikes_distance_landed=0,
                    sig_strikes_distance_attempted=4,
                    sig_strikes_clinch_landed=0,
                    sig_strikes_clinch_attempted=0,
                    sig_strikes_grounded_landed=0,
                    sig_strikes_grounded_attempted=0,
                ),
                RoundSigStats(
                    fight_uid="6a060498e60756af",
                    fighter_uid="63b65af1c5cb02cb",
                    round_num=2,
                    sig_strikes_landed=0,
                    sig_strikes_attempted=2,
                    sig_strikes_head_landed=0,
                    sig_strikes_head_attempted=2,
                    sig_strikes_body_landed=0,
                    sig_strikes_body_attempted=0,
                    sig_strikes_leg_landed=0,
                    sig_strikes_leg_attempted=0,
                    sig_strikes_distance_landed=0,
                    sig_strikes_distance_attempted=2,
                    sig_strikes_clinch_landed=0,
                    sig_strikes_clinch_attempted=0,
                    sig_strikes_grounded_landed=0,
                    sig_strikes_grounded_attempted=0,
                ),
                RoundSigStats(
                    fight_uid="6a060498e60756af",
                    fighter_uid="c670aa48827d6be6",
                    round_num=3,
                    sig_strikes_landed=3,
                    sig_strikes_attempted=16,
                    sig_strikes_head_landed=2,
                    sig_strikes_head_attempted=13,
                    sig_strikes_body_landed=0,
                    sig_strikes_body_attempted=0,
                    sig_strikes_leg_landed=1,
                    sig_strikes_leg_attempted=3,
                    sig_strikes_distance_landed=2,
                    sig_strikes_distance_attempted=12,
                    sig_strikes_clinch_landed=1,
                    sig_strikes_clinch_attempted=4,
                    sig_strikes_grounded_landed=0,
                    sig_strikes_grounded_attempted=0,
                ),
                RoundSigStats(
                    fight_uid="6a060498e60756af",
                    fighter_uid="63b65af1c5cb02cb",
                    round_num=3,
                    sig_strikes_landed=4,
                    sig_strikes_attempted=15,
                    sig_strikes_head_landed=3,
                    sig_strikes_head_attempted=14,
                    sig_strikes_body_landed=1,
                    sig_strikes_body_attempted=1,
                    sig_strikes_leg_landed=0,
                    sig_strikes_leg_attempted=0,
                    sig_strikes_distance_landed=3,
                    sig_strikes_distance_attempted=14,
                    sig_strikes_clinch_landed=1,
                    sig_strikes_clinch_attempted=1,
                    sig_strikes_grounded_landed=0,
                    sig_strikes_grounded_attempted=0,
                ),
            ],
            issues=[],
            uid="6a060498e60756af",
        )
    ]
    _run_sig_stats(fight_dir, expected_results)


def test_title_details(fight_dir):
    expected_results: list[FightDetailsParsingResult] = [
        FightDetailsParsingResult(
            result=UFCFight(
                event_uid="b60391da771deefe",
                fight_uid="f29eec19aa5c1303",
                fight_style=FightStyle.MMA,
                fight_type=FightType.TITLE,
                fight_division=UFCDivisionNames.OPEN_WEIGHT,
                fighter1_uid="429e7d3725852ce9",
                fighter2_uid="c670aa48827d6be6",
                fighter1_result=FightResult.WIN,
                fighter2_result=FightResult.LOSS,
                decision=Decision.SUB,
                decision_round=1,
                decision_time_seconds=949,
                referee="John McCarthy",
            ),
            issues=[],
            uid="f29eec19aa5c1303",
        ),
        FightDetailsParsingResult(
            result=UFCFight(
                event_uid="a6a9ab5a824e8f66",
                fight_uid="00835554f95fa911",
                fight_style=FightStyle.MMA,
                fight_type=FightType.TITLE,
                fight_division=UFCDivisionNames.OPEN_WEIGHT,
                fighter1_uid="429e7d3725852ce9",
                fighter2_uid="46c8ec317aff28ac",
                fighter1_result=FightResult.WIN,
                fighter2_result=FightResult.LOSS,
                decision=Decision.TKO,
                decision_round=1,
                decision_time_seconds=77,
                referee="John McCarthy",
            ),
            issues=[],
            uid="00835554f95fa911",
        ),
    ]
    _run_test_parse_details(fight_dir, expected_results)


def test_title_total_stats(fight_dir):
    expected_results: list[TotalStatsParsingResult] = [
        TotalStatsParsingResult(
            issues=[],
            uid="f29eec19aa5c1303",
            result=[
                RoundTotalStats(
                    fight_uid="f29eec19aa5c1303",
                    fighter_uid="429e7d3725852ce9",
                    round_num=1,
                    knockdowns=0,
                    total_strikes_landed=80,
                    total_strikes_attempted=84,
                    takedowns_landed=0,
                    takedowns_attempted=0,
                    submissions_attempted=3,
                    reversals=0,
                    control_time_seconds=None,
                ),
                RoundTotalStats(
                    fight_uid="f29eec19aa5c1303",
                    fighter_uid="c670aa48827d6be6",
                    round_num=1,
                    knockdowns=0,
                    total_strikes_landed=27,
                    total_strikes_attempted=43,
                    takedowns_landed=1,
                    takedowns_attempted=1,
                    submissions_attempted=0,
                    reversals=0,
                    control_time_seconds=None,
                ),
            ],
        ),
        TotalStatsParsingResult(
            uid="00835554f95fa911",
            issues=[],
            result=[
                RoundTotalStats(
                    fight_uid="00835554f95fa911",
                    fighter_uid="429e7d3725852ce9",
                    round_num=1,
                    knockdowns=0,
                    total_strikes_landed=11,
                    total_strikes_attempted=11,
                    takedowns_landed=1,
                    takedowns_attempted=2,
                    submissions_attempted=0,
                    reversals=0,
                    control_time_seconds=None,
                ),
                RoundTotalStats(
                    fight_uid="00835554f95fa911",
                    fighter_uid="46c8ec317aff28ac",
                    round_num=1,
                    knockdowns=0,
                    total_strikes_landed=2,
                    total_strikes_attempted=3,
                    takedowns_landed=0,
                    takedowns_attempted=0,
                    submissions_attempted=0,
                    reversals=0,
                    control_time_seconds=None,
                ),
            ],
        ),
    ]
    _run_total_stats(fight_dir, expected_results)


def test_title_sig_stats(fight_dir):
    expected_results: list[SigStatsParsingResult] = [
        SigStatsParsingResult(
            uid="f29eec19aa5c1303",
            issues=[],
            result=[
                RoundSigStats(
                    fight_uid="f29eec19aa5c1303",
                    fighter_uid="429e7d3725852ce9",
                    round_num=1,
                    sig_strikes_landed=0,
                    sig_strikes_attempted=4,
                    sig_strikes_head_landed=0,
                    sig_strikes_head_attempted=1,
                    sig_strikes_body_landed=0,
                    sig_strikes_body_attempted=0,
                    sig_strikes_leg_landed=0,
                    sig_strikes_leg_attempted=3,
                    sig_strikes_distance_landed=0,
                    sig_strikes_distance_attempted=4,
                    sig_strikes_clinch_landed=0,
                    sig_strikes_clinch_attempted=0,
                    sig_strikes_grounded_landed=0,
                    sig_strikes_grounded_attempted=0,
                ),
                RoundSigStats(
                    fight_uid="f29eec19aa5c1303",
                    fighter_uid="c670aa48827d6be6",
                    round_num=1,
                    sig_strikes_landed=4,
                    sig_strikes_attempted=7,
                    sig_strikes_head_landed=4,
                    sig_strikes_head_attempted=7,
                    sig_strikes_body_landed=0,
                    sig_strikes_body_attempted=0,
                    sig_strikes_leg_landed=0,
                    sig_strikes_leg_attempted=0,
                    sig_strikes_distance_landed=0,
                    sig_strikes_distance_attempted=0,
                    sig_strikes_clinch_landed=0,
                    sig_strikes_clinch_attempted=0,
                    sig_strikes_grounded_landed=4,
                    sig_strikes_grounded_attempted=7,
                ),
            ],
        ),
        SigStatsParsingResult(
            uid="00835554f95fa911",
            issues=[],
            result=[
                RoundSigStats(
                    fight_uid="00835554f95fa911",
                    fighter_uid="429e7d3725852ce9",
                    round_num=1,
                    sig_strikes_landed=4,
                    sig_strikes_attempted=4,
                    sig_strikes_head_landed=3,
                    sig_strikes_head_attempted=3,
                    sig_strikes_body_landed=0,
                    sig_strikes_body_attempted=0,
                    sig_strikes_leg_landed=1,
                    sig_strikes_leg_attempted=1,
                    sig_strikes_distance_landed=0,
                    sig_strikes_distance_attempted=0,
                    sig_strikes_clinch_landed=1,
                    sig_strikes_clinch_attempted=1,
                    sig_strikes_grounded_landed=3,
                    sig_strikes_grounded_attempted=3,
                ),
                RoundSigStats(
                    fight_uid="00835554f95fa911",
                    fighter_uid="46c8ec317aff28ac",
                    round_num=1,
                    sig_strikes_landed=1,
                    sig_strikes_attempted=2,
                    sig_strikes_head_landed=0,
                    sig_strikes_head_attempted=0,
                    sig_strikes_body_landed=1,
                    sig_strikes_body_attempted=2,
                    sig_strikes_leg_landed=0,
                    sig_strikes_leg_attempted=0,
                    sig_strikes_distance_landed=0,
                    sig_strikes_distance_attempted=1,
                    sig_strikes_clinch_landed=1,
                    sig_strikes_clinch_attempted=1,
                    sig_strikes_grounded_landed=0,
                    sig_strikes_grounded_attempted=0,
                ),
            ],
        ),
    ]
    _run_sig_stats(fight_dir, expected_results)


@pytest.fixture
def fight_dir() -> Path:
    return Path(__file__).parents[1] / "data/raw/ufc/fights"
