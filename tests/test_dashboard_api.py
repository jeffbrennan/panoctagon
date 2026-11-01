from __future__ import annotations

import math
from pathlib import Path
from functools import lru_cache

import pytest
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
