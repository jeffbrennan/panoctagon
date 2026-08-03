from pathlib import Path

import pytest

from panoctagon.boxing.parse.events import parse_event_page
from panoctagon.boxing.scrape.events import parse_schedule
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
