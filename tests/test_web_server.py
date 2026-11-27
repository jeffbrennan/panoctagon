from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from panoctagon.web.server import create_app


@pytest.fixture
def client(tmp_path: Path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>Panoctagon</title>")
    (tmp_path / "assets" / "index-AbCd1234.js").write_text(
        'export const name = "panoctagon";' * 200
    )
    (tmp_path / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    with TestClient(create_app(tmp_path)) as client:
        yield client


def test_serves_index_and_api_on_the_same_origin(client):
    response = client.get("/?view=fighters&fighter=alpha")
    assert response.status_code == 200
    assert "Panoctagon" in response.text
    assert response.headers["cache-control"] == "no-cache"
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/docs").status_code == 200


def test_hashed_assets_are_compressed_and_immutable(client):
    response = client.get("/assets/index-AbCd1234.js", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "Accept-Encoding" in response.headers["vary"]
    assert response.text.startswith("export const name")
    assert client.get("/favicon.svg").headers["cache-control"] == "no-cache"


def test_unknown_api_and_static_paths_stay_404(client):
    assert client.get("/api/not-an-endpoint").status_code == 404
    assert client.get("/not-a-route").status_code == 404
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/assets/%2e%2e/%2e%2e/outside.txt").status_code == 404


def test_readiness_requires_build_and_usable_database(tmp_path: Path, monkeypatch):
    from tests.dashboard_seed import seed_dashboard
    database = tmp_path / 'test.duckdb'
    seed_dashboard(database)
    monkeypatch.setenv('PANOCTAGON_API_DATABASE', str(database))
    build = tmp_path / 'build'
    build.mkdir()
    with TestClient(create_app(build)) as client:
        assert client.get('/healthz').status_code == 200
        assert client.get('/readyz').status_code == 503
        (build / 'index.html').write_text('ready')
        assert client.get('/readyz').status_code == 200
        database.unlink()
        assert client.get('/readyz').status_code == 503
