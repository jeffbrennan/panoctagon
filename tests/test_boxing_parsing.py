from pathlib import Path

import pytest

from panoctagon.boxing.parse.events import (
    apply_match_results,
    parse_event_page,
    parse_match_page,
)
from panoctagon.boxing.parse.fighters import parse_fighter
from panoctagon.boxing.scrape.events import parse_results, parse_schedule
from panoctagon.enums import FightResult
from panoctagon.models import FileContents
from panoctagon.tables import BoxingEvent, BoxingFight

import datetime


@pytest.fixture
def boxing_data_dir() -> Path:
    return Path(__file__).parents[1] / "data/raw/boxing"


@pytest.fixture
def schedule_html(boxing_data_dir: Path) -> str:
    schedule_file = boxing_data_dir / "schedule.html"
    if not schedule_file.exists():
        pytest.skip("boxing schedule fixture not downloaded; run `boxing scrape events` first")
    return schedule_file.read_text()


def _event_page(
    boxing_data_dir: Path, uid: str, file_num: int = 0, n_files: int = 1
) -> FileContents:
    page = boxing_data_dir / "events" / f"{uid}.html"
    if not page.exists():
        pytest.skip(f"boxing event fixture {uid} not downloaded")
    return FileContents(
        uid=uid,
        path=page,
        modified_ts=datetime.datetime(2026, 8, 2, 12, 0, 0),
        contents=page.read_text(),
        file_num=file_num,
        n_files=n_files,
    )


def _fighter_page(
    boxing_data_dir: Path, uid: str, file_num: int = 0, n_files: int = 1
) -> FileContents:
    page = boxing_data_dir / "fighters" / f"{uid}.html"
    if not page.exists():
        pytest.skip(f"boxing fighter fixture {uid} not downloaded")
    return FileContents(
        uid=uid,
        path=page,
        modified_ts=datetime.datetime(2026, 8, 2, 12, 0, 0),
        contents=page.read_text(),
        file_num=file_num,
        n_files=n_files,
    )


def test_parse_schedule_counts_all_upcoming_events(schedule_html: str) -> None:
    events = parse_schedule(schedule_html)
    assert len(events) == 12


def test_parse_schedule_main_event_details(schedule_html: str) -> None:
    events = parse_schedule(schedule_html)
    by_uid = {e.event_uid: e for e in events}

    garcia = by_uid["3846"]
    assert garcia.title == "Conor Benn vs. Ryan Garcia"
    assert garcia.event_date == "2026-09-12"
    assert garcia.event_location == "Las Vegas, Nevada, USA"
    assert garcia.broadcast == "7pm ET Paramount+"

    pacquiao = by_uid["3794"]
    assert pacquiao.title == "Manny Pacquiao vs. Floyd Mayweather Jr"
    assert pacquiao.event_date == "2026-09-19"
    assert pacquiao.event_location == "The Sphere, Las Vegas, Nevada, USA"
    assert pacquiao.broadcast == "TBA NetFlix"


def test_parse_schedule_orders_events_by_date(schedule_html: str) -> None:
    events = parse_schedule(schedule_html)
    assert all(events[i].event_date <= events[i + 1].event_date for i in range(len(events) - 1))
    assert all(isinstance(e, BoxingEvent) for e in events)


def test_parse_event_page_main_bout(boxing_data_dir: Path) -> None:
    result = parse_event_page(_event_page(boxing_data_dir, "3846"))
    assert result.issues == []

    assert len(result.result) == 1
    fight = result.result[0]
    assert fight.event_uid == "3846"
    assert fight.fight_uid == "9730"
    assert fight.match_uid == "9730"
    assert fight.fighter1_uid == "4278"
    assert fight.fighter2_uid == "4961"
    assert fight.title_bout == "WBC World Welter"
    assert fight.scheduled_rounds == 12
    assert fight.main_event is True
    assert fight.bout_order == 1


def test_parse_event_page_details(boxing_data_dir: Path) -> None:
    result = parse_event_page(_event_page(boxing_data_dir, "3838"))
    event = result.event
    assert event is not None
    assert event.event_uid == "3838"
    assert event.event_date == "2026-09-12"
    assert event.event_location == "Riyadh, Saudi Arabia"
    assert event.broadcast == "DAZN PPV"
    assert event.bouts == 1
    assert isinstance(event.image_url, str)
    assert event.image_url.startswith("http")


def test_parse_event_page_different_division(boxing_data_dir: Path) -> None:
    result = parse_event_page(_event_page(boxing_data_dir, "3838"))
    fight = result.result[0]
    assert fight.title_bout == "WBC World Super Middle"
    assert fight.fighter1_uid == "1336"
    assert fight.fighter2_uid == "5898"


def test_parse_event_page_all_fights_are_boxing_fights(boxing_data_dir: Path) -> None:
    for uid in ["3838", "3846"]:
        result = parse_event_page(_event_page(boxing_data_dir, uid))
        assert all(isinstance(f, BoxingFight) for f in result.result)


def test_parse_fighter_details(boxing_data_dir: Path) -> None:
    result = parse_fighter(_fighter_page(boxing_data_dir, "4961"))
    fighter = result.result
    assert fighter.fighter_uid == "4961"
    assert fighter.first_name == "Ryan"
    assert fighter.last_name == "Garcia"
    assert fighter.nickname == "Kingry"
    assert fighter.weight_class == "Super featherweight"
    assert fighter.stance == "Orthodox"
    assert fighter.height_inches == 70
    assert fighter.reach_inches == 70
    assert fighter.nationality == "Los Angeles, California, USA"
    assert fighter.dob == "1998-08-08"
    assert fighter.wins == 25
    assert fighter.losses == 2
    assert fighter.draws == 0
    assert fighter.kos == 20
    assert fighter.ko_percent == 74.0
    assert fighter.total_bouts == 27


def test_parse_fighter_missing_reach(boxing_data_dir: Path) -> None:
    result = parse_fighter(_fighter_page(boxing_data_dir, "4278"))
    fighter = result.result
    assert fighter.first_name == "Conor"
    assert fighter.last_name == "Benn"
    assert fighter.wins == 23
    assert fighter.losses == 1
    assert fighter.reach_inches is None
    assert fighter.height_inches == 68


def test_parse_fight_history_first_entry(boxing_data_dir: Path) -> None:
    result = parse_fighter(_fighter_page(boxing_data_dir, "4961"))
    history = result.fight_history
    assert len(history) == 16

    first = history[0]
    assert first.boxer_uid == "4961"
    assert first.event_uid == "3785"
    assert first.fight_date == "2026-02-21"
    assert first.opponent_uid == "3972"
    assert first.boxer_result == FightResult.WIN
    assert first.opponent_result == FightResult.LOSS
    assert first.decision == "UD"
    assert first.decision_round == 12
    assert first.title_bout == "WBC World Welterweight"
    assert first.boxer_weight_lbs == 147.0
    assert first.opponent_weight_lbs == 147.0
    assert "Tim Cheatham" in (first.judge_cards or "")
    assert "T-Mobile Arena" in (first.venue or "")


def test_parse_fight_history_fractional_weights(boxing_data_dir: Path) -> None:
    result = parse_fighter(_fighter_page(boxing_data_dir, "4961"))
    fractional = [
        h for h in result.fight_history if h.boxer_weight_lbs and h.boxer_weight_lbs % 1 != 0
    ]
    assert len(fractional) > 0
    assert all(h.boxer_weight_lbs in (129.5, 130.5, 134.25, 134.75) for h in fractional)


def test_parse_fight_history_skips_incomplete_fights(boxing_data_dir: Path) -> None:
    result = parse_fighter(_fighter_page(boxing_data_dir, "3012"))
    fight_dates = [h.fight_date for h in result.fight_history]
    assert "2014-09-20" not in fight_dates
    assert all(h.boxer_result is not None for h in result.fight_history)


def test_parse_fight_history_results_direction(boxing_data_dir: Path) -> None:
    result = parse_fighter(_fighter_page(boxing_data_dir, "4278"))
    assert all(
        h.boxer_result != h.opponent_result
        and h.boxer_result in (FightResult.WIN, FightResult.LOSS)
        for h in result.fight_history
    )


def test_parse_event_page_extracts_title(boxing_data_dir: Path) -> None:
    result = parse_event_page(_event_page(boxing_data_dir, "3846"))
    assert result.event is not None
    assert result.event.title == "Ryan Garcia vs Conor Benn WBC World Welterweight"


def test_parse_match_page_outcomes_and_decision() -> None:
    page = FileContents(
        uid="9730",
        path=Path("9730.html"),
        modified_ts=datetime.datetime.now(),
        contents="""
            <ul class="list-group"><li class="list-group-item">
              <a href="/boxer-4278">Conor Benn</a>
              <span style="color:red">L</span>
              <a href="/boxer-4961">Ryan Garcia</a>
              <span style="color:green">W</span>
              <span style="color:#3366CC">UD 12</span>
            </li></ul>
        """,
        file_num=0,
        n_files=1,
    )
    result = parse_match_page(page)
    assert result.issues == []
    assert result.result.fighter1_result == FightResult.LOSS
    assert result.result.fighter2_result == FightResult.WIN
    assert result.result.decision == "UD"
    assert result.result.decision_round == 12


def test_apply_match_results_handles_reversed_fighters() -> None:
    page = FileContents(
        uid="9730",
        path=Path("9730.html"),
        modified_ts=datetime.datetime.now(),
        contents="""
            <a href="/boxer-4278">Conor Benn</a><span style="color:red">L</span>
            <a href="/boxer-4961">Ryan Garcia</a><span style="color:green">W</span>
            <span style="color:#3366CC">UD 12</span>
        """,
        file_num=0,
        n_files=1,
    )
    match = parse_match_page(page)
    fight = BoxingFight(
        event_uid="3846",
        fight_uid="9730",
        fighter1_uid="4961",
        fighter2_uid="4278",
        match_uid="9730",
    )
    apply_match_results([fight], [match])
    assert fight.fighter1_result == FightResult.WIN
    assert fight.fighter2_result == FightResult.LOSS
    assert fight.decision_round == 12


def test_parse_results_discovers_completed_events() -> None:
    events = parse_results(
        """
        <div class="panel">
          <div class="well-content"><h5>Sun, Jul 26 2026
            <i class="fa-map-marker"></i> Las Vegas, Nevada, USA</h5></div>
          <ul class="list-group"><li class="list-group-item">bout</li></ul>
          <a href="/event-3785">View FightNight</a>
        </div>
        """
    )
    assert len(events) == 1
    assert events[0].event_uid == "3785"
    assert events[0].event_date == "2026-07-26"
    assert events[0].event_location == "Las Vegas, Nevada, USA"
    assert events[0].bouts == 1
