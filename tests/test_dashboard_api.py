from __future__ import annotations

import math
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from panoctagon.api import analytics, queries
from panoctagon.api.server import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "dashboard.duckdb"
    with duckdb.connect(str(path)) as db:
        db.execute("""
            create table ufc_fighters (
                fighter_uid varchar, first_name varchar, last_name varchar, nickname varchar,
                dob varchar, place_of_birth varchar, stance varchar, style varchar,
                height_inches int, reach_inches int, leg_reach_inches int
            );
            insert into ufc_fighters values
                ('alpha', 'Alex', 'Alpha', 'A', '1990-01-01', null, 'Orthodox', null, 72, 74, null),
                ('bravo', 'Blair', 'Bravo', null, '1995-01-01', null, 'Southpaw', null, 70, 70, null),
                ('charlie', 'Casey', 'Charlie', null, null, null, null, null, null, null, null);
            create table ufc_events (event_uid varchar, title varchar, event_date varchar,
                event_location varchar, downloaded_ts varchar);
            insert into ufc_events values
                ('past', 'UFC Test', '2024-01-01', 'Test City', '2024-01-02T00:00:00'),
                ('future', 'UFC Future', '2099-01-01', 'Test City', '2024-01-03T00:00:00');
            create table ufc_fights (fight_uid varchar, event_uid varchar,
                fighter1_uid varchar, fighter2_uid varchar, fighter1_result varchar,
                fighter2_result varchar, fight_division varchar, fight_type varchar,
                decision varchar, decision_round int, fight_order int);
            insert into ufc_fights
                select 'fight' || cast(i as varchar), 'past', 'alpha', 'bravo',
                    case when i < 5 then 'WIN' else 'LOSS' end,
                    case when i < 5 then 'LOSS' else 'WIN' end,
                    'MIDDLEWEIGHT', 'REGULAR', 'TKO', 1, i from range(1, 6) t(i);
            insert into ufc_fights values
                ('upcoming', 'future', 'alpha', 'charlie', null, null, 'MIDDLEWEIGHT', 'REGULAR', null, null, 1),
                ('missingstats', 'past', 'alpha', 'charlie', 'NO_CONTEST', 'NO_CONTEST', 'HEAVYWEIGHT', 'REGULAR', 'DQ', 1, 6);
            create table ufc_fight_stats (fight_uid varchar, fighter_uid varchar, round_num int,
                total_strikes_landed int, total_strikes_attempted int,
                sig_strikes_landed int, sig_strikes_attempted int,
                sig_strikes_head_landed int, sig_strikes_body_landed int, sig_strikes_leg_landed int,
                takedowns_landed int, control_time_seconds int);
            insert into ufc_fight_stats
                select 'fight' || cast(i as varchar), 'alpha', 1, 30, 60, 20, 40, 10, 6, 4, 1, 50 from range(1, 6) t(i);
            insert into ufc_fight_stats
                select 'fight' || cast(i as varchar), 'bravo', 1, 10, 40, 10, 25, 5, 3, 2, 0, 0 from range(1, 6) t(i);
            create table bfo_ufc_link (fight_uid varchar, fighter_uid varchar, match_id int, fighter varchar);
            create table bfo_parsed_odds (match_id int, fighter varchar, closing_odds int, event_date varchar, slug varchar);
            insert into bfo_ufc_link values ('fight1', 'alpha', 1, 'alpha'), ('upcoming', 'alpha', 2, 'alpha');
            insert into bfo_parsed_odds values
                (1, 'alpha', -110, '2023-12-30', 'old'), (1, 'alpha', -150, '2024-01-01', 'new'),
                (2, 'alpha', -200, '2098-12-30', 'future');
        """)
    engine = create_engine(
        f"duckdb:///{path}", poolclass=NullPool, connect_args={"read_only": True}
    )
    monkeypatch.setattr(analytics, "get_read_engine", lambda: engine)
    monkeypatch.setattr(queries, "get_read_engine", lambda: engine)
    analytics._cached_rows.cache_clear()
    analytics._network.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    analytics._cached_rows.cache_clear()
    analytics._network.cache_clear()
    engine.dispose()


def test_metadata_counts_completed_fights(client):
    assert client.get("/metadata").json() == {
        "last_refresh": "2024-01-03",
        "fighters": 3,
        "fights": 6,
        "first_year": 2024,
        "last_year": 2099,
    }


def test_profile_keeps_fights_without_stats_and_uses_latest_odds(client):
    response = client.get("/fighter/alpha/analytics")
    assert response.status_code == 200
    profile = response.json()
    assert profile["record"] == {
        "wins": 4,
        "losses": 1,
        "draws": 0,
        "no_contests": 1,
        "total_fights": 6,
    }
    assert len(profile["fights"]) == 6
    first = next(f for f in profile["fights"] if f["fight_uid"] == "fight1")
    assert first["closing_odds"] == -150
    assert first["strikes_landed"] == 30
    assert first["strikes_absorbed"] == 10
    missing = next(f for f in profile["fights"] if f["fight_uid"] == "missingstats")
    assert missing["strikes_landed"] is None
    assert client.get("/fighter/notfound/analytics").status_code == 404


def test_network_aggregates_rematches_and_excludes_upcoming(client):
    data = client.get(
        "/analytics/network?division=MIDDLEWEIGHT&start_year=2024&end_year=2024"
    ).json()
    assert len(data["nodes"]) == 2
    assert len(data["links"]) == 1
    assert data["links"][0]["fights"] == 5
    alpha = next(n for n in data["nodes"] if n["id"] == "alpha")
    assert (alpha["wins"], alpha["losses"], alpha["fights"]) == (4, 1, 5)
    assert all(math.isfinite(n["x"]) and math.isfinite(n["y"]) for n in data["nodes"])
    assert client.get("/analytics/network?start_year=2026&end_year=2024").status_code == 422
    assert client.get(
        "/analytics/network?division=MIDDLEWEIGHT&start_year=2025&end_year=2026"
    ).json() == {"nodes": [], "links": []}


def test_roster_filters_division_and_preserves_round_medians(client):
    data = client.get("/analytics/roster?division=MIDDLEWEIGHT").json()
    assert len(data["fighters"]) == 2
    alpha = next(f for f in data["fighters"] if f["fighter_uid"] == "alpha")
    assert alpha["landed"] == 30
    assert alpha["absorbed"] == 10
    assert alpha["opposition_strength"] == 4
    head = next(t for t in data["targets"] if t["target"] == "Head" and t["result"] == "WIN")
    assert head["count"] == 5
    assert head["values"] == [50] * 5
    assert client.get("/analytics/roster?division=FLYWEIGHT").json()["fighters"] == []


def test_upcoming_includes_odds_and_experience_without_duplicate_fights(client):
    data = client.get("/upcoming").json()
    assert len(data) == 1
    assert len(data[0]["fights"]) == 1
    matchup = data[0]["fights"][0]
    assert matchup["fighter1_closing_odds"] == -200
    assert matchup["fighter1_total_fights"] == 6
    assert matchup["fighter2_total_fights"] == 1


def test_headshots_reject_path_characters(client):
    assert client.get("/fighter/%2e%2e/headshot").status_code == 404
    assert client.get("/fighter/alpha/headshot").status_code == 404
