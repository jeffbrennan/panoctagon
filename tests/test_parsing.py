from panoctagon.ufc.scrape_fights import (
    parse_fight,
    FightContents,
    FightParsingResult,
    FightDetailsParsingResult,
    get_fight_html_files,
    Fight,
    FightStyle,
    FightType,
    FightResult,
    Decision,
    RoundTotalStats,
    RoundSigStats,
)


def _test_parsing(fight_contents: FightContents, expected: FightParsingResult):
    actual = parse_fight(fight_contents)
    fight_result_matches = actual.fight_result == expected.fight_result
    sig_stats_match = actual.sig_stats == expected.sig_stats
    total_stats_match = actual.total_stats == expected.total_stats

    if not fight_result_matches:
        print(actual.fight_result)
        print("-----")
        print(expected.fight_result)
        assert fight_result_matches

    if not sig_stats_match:
        print(actual.sig_stats)
        print("-----")
        print(expected.sig_stats)
        assert sig_stats_match

    if not total_stats_match:
        print(actual.total_stats)
        print("----")
        print(expected.total_stats)
        assert total_stats_match


def test_superfight():
    expected_results: list[FightParsingResult] = [
        FightParsingResult(
            fight_uid="6a060498e60756af",
            fight_result=FightDetailsParsingResult(
                fight=Fight(
                    event_uid="a390eb8a9b2df298",
                    fight_uid="6a060498e60756af",
                    fight_style=FightStyle.MMA,
                    fight_type=FightType.TITLE,
                    fighter1_uid="c670aa48827d6be6",
                    fighter2_uid="63b65af1c5cb02cb",
                    fighter1_result=FightResult.WIN,
                    fighter2_result=FightResult.LOSS,
                    decision=Decision.SPLIT_DECISION,
                    decision_round=3,
                    decision_time_seconds=180,
                    referee="John McCarthy",
                ),
                parsing_issues=[],
            ),
            total_stats=[
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
            sig_stats=[
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
            file_issues=[],
        )
    ]
    for expected in expected_results:
        fight_contents = get_fight_html_files(expected.fight_uid)
        assert len(fight_contents) == 1
        _test_parsing(fight_contents[0], expected)


def test_title():
    expected_results: list[FightParsingResult] = [
        FightParsingResult(
            fight_uid="f29eec19aa5c1303",
            fight_result=None,
            total_stats=None,
            sig_stats=None,
            file_issues=[],
        ),
        FightParsingResult(
            fight_uid="00835554f95fa911",
            fight_result=None,
            total_stats=None,
            sig_stats=None,
            file_issues=[],
        ),
    ]

    for expected in expected_results:
        fight_contents = get_fight_html_files(expected.fight_uid)
        assert len(fight_contents) == 1
        _test_parsing(fight_contents[0], expected)
