from __future__ import annotations

import math
from pathlib import Path
from functools import lru_cache

import pytest
import duckdb
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from tests.dashboard_seed import seed_dashboard

from panoctagon.api import analytics, queries
from panoctagon.api.server import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    path = tmp_path / "dashboard.duckdb"
    seed_dashboard(path, getattr(request, "param", None) == "outlier")
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
        "revision": None,
        "published_at": None,
        "current_year": analytics.current_year(),
        "last_refresh": "2024-01-03",
        "fighters": 3,
        "fights": 6,
        "first_year": 2024,
        "last_year": 2099,
        "default_fighter_uid": "alpha",
    }


def test_metadata_prefers_max_holloway_as_default_fighter(client, tmp_path):
    with duckdb.connect(str(tmp_path / "dashboard.duckdb")) as db:
        db.execute(
            "insert into ufc_fighters values ('holloway', 'Max', 'Holloway', 'Blessed', null, null, 'Orthodox', null, 71, 69, null)"
        )
    analytics._cached_rows.cache_clear()
    assert client.get("/metadata").json()["default_fighter_uid"] == "holloway"


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
    assert data["links"][0]["source_wins"] == 4
    assert data["links"][0]["target_wins"] == 1
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


@pytest.mark.parametrize("client", ["outlier"], indirect=True)
def test_target_boxes_use_tukey_whiskers_and_preserve_outlier_context(client):
    data = client.get("/analytics/roster?division=MIDDLEWEIGHT").json()
    head = next(t for t in data["targets"] if t["target"] == "Head" and t["result"] == "WIN")
    assert head["values"] == [50] * 5
    assert head["outliers"] == [
        {
            "value": 0,
            "fighter_uid": "alpha",
            "fighter_name": "Alex Alpha",
            "event_title": "UFC Test",
            "event_date": "2024-01-01",
        }
    ]


def test_network_default_range_uses_current_utc_year(client, monkeypatch):
    monkeypatch.setattr(analytics, "current_year", lambda: 2027)
    calls = []
    monkeypatch.setattr(analytics, "_network", lru_cache()(lambda division, start, end, period, revision: calls.append((start, end)) or {"nodes": [], "links": []}))
    assert client.get("/metadata").json()["current_year"] == 2027
    assert client.get("/analytics/network").status_code == 200
    assert calls == [(2022, 2027)]


def test_same_day_tournament_fights_follow_reverse_card_order(client, tmp_path):
    # UFC 2's source card lists the final first: lower numbers are later bouts.
    with duckdb.connect(str(tmp_path / "dashboard.duckdb")) as db:
        db.execute("""
            insert into ufc_fights values
              ('a_final', 'past', 'alpha', 'bravo', 'WIN', 'LOSS', 'MIDDLEWEIGHT', 'REGULAR', 'TKO', 1, 1),
              ('z_first', 'past', 'alpha', 'charlie', 'WIN', 'LOSS', 'MIDDLEWEIGHT', 'REGULAR', 'TKO', 1, 15)
        """)
    profile = client.get('/fighter/alpha/analytics').json()
    order = [fight['fight_uid'] for fight in profile['fights']]
    assert order.index('z_first') < order.index('a_final')


def test_polars_free_query_endpoints_and_404s(client):
    fighters = client.get("/fighter?name=alpha").json()
    assert [f["fighter_uid"] for f in fighters] == ["alpha"]

    detail = client.get("/fighter/alpha").json()
    assert detail["bio"]["full_name"] == "Alex Alpha"
    assert detail["record"]["wins"] == 4
    assert len(detail["recent_fights"]) == 7
    assert client.get("/fighter/notfound").status_code == 404

    fights = client.get("/fighter/alpha/fights?limit=3").json()
    assert len(fights) == 3

    events = client.get("/events?limit=10").json()
    assert {e["event_uid"] for e in events} == {"past", "future"}
    assert [e["event_uid"] for e in client.get("/events?upcoming_only=true").json()] == ["future"]
    assert [e["event_uid"] for e in client.get("/event/search?name=Future").json()] == ["future"]

    event_detail = client.get("/event/past").json()
    assert event_detail["title"] == "UFC Test"
    assert len(event_detail["fights"]) == 6
    assert client.get("/event/notfound").status_code == 404

    assert client.get("/divisions").json() == ["HEAVYWEIGHT", "MIDDLEWEIGHT"]


def test_spring_layout_handles_large_components_without_scipy():
    nodes = [f"f{i}" for i in range(510)]
    adjacency = {uid: [] for uid in nodes}
    for i in range(len(nodes) - 1):
        adjacency[nodes[i]].append(nodes[i + 1])
        adjacency[nodes[i + 1]].append(nodes[i])
    positions = analytics._spring_layout(nodes, adjacency, seed=42, iterations=5, scale=400.0)
    assert len(positions) == 510
    assert all(math.isfinite(x) and math.isfinite(y) for x, y in positions.values())
