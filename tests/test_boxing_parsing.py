from pathlib import Path

import pytest

from panoctagon.boxing.scrape.events import parse_schedule
from panoctagon.tables import BoxingEvent


@pytest.fixture
def boxing_data_dir() -> Path:
    return Path(__file__).parents[1] / "data/raw/boxing"


@pytest.fixture
def schedule_html(boxing_data_dir: Path) -> str:
    schedule_file = boxing_data_dir / "schedule.html"
    if not schedule_file.exists():
        pytest.skip("boxing schedule fixture not downloaded; run `boxing scrape events` first")
    return schedule_file.read_text()


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
