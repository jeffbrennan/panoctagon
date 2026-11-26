import json
from pathlib import Path

import duckdb
import pytest

from panoctagon.api.snapshots import publish_snapshot
from tests.dashboard_seed import seed_dashboard


def test_publish_checkpoints_and_keeps_previous_revision_after_failure(tmp_path: Path):
    working = tmp_path / 'working.duckdb'
    seed_dashboard(working)
    directory = tmp_path / 'published'
    first = publish_snapshot(working, directory)
    with duckdb.connect(str(working)) as db:
        db.execute("insert into ufc_events values ('new', 'New', '2099-01-02', 'City', '2025')")
    second = publish_snapshot(working, directory)
    assert first['revision'] != second['revision']
    with duckdb.connect(str(directory / first['file']), read_only=True) as db:
        assert db.execute('select count(*) from ufc_events').fetchone()[0] == 2
    with duckdb.connect(str(directory / second['file']), read_only=True) as db:
        assert db.execute('select count(*) from ufc_events').fetchone()[0] == 3
    with duckdb.connect(str(working)) as db:
        db.execute('drop table ufc_events')
    with pytest.raises(duckdb.CatalogException):
        publish_snapshot(working, directory)
    assert json.loads((directory / 'manifest.json').read_text()) == second
    assert len(list(directory.glob('*.duckdb'))) == 2


def test_api_switches_revisions_and_isolates_cached_metadata(tmp_path: Path, monkeypatch):
    from fastapi.testclient import TestClient
    from panoctagon.api import analytics
    from panoctagon.api.server import app

    working = tmp_path / 'working.duckdb'
    directory = tmp_path / 'published'
    seed_dashboard(working)
    first = publish_snapshot(working, directory)
    monkeypatch.setenv('PANOCTAGON_API_SNAPSHOT_DIR', str(directory))
    analytics._cached_rows.cache_clear()
    clock = [100.0]
    monkeypatch.setattr(analytics.time, 'monotonic', lambda: clock[0])
    with TestClient(app) as client:
        assert client.get('/metadata').json()['revision'] == first['revision']
        misses_after_first = analytics._cached_rows.cache_info().misses
        clock[0] += 600.0  # advance past legacy 120 s rollover bucket
        assert client.get('/metadata').json()['fighters'] == 3
        assert analytics._cached_rows.cache_info().misses == misses_after_first
        with duckdb.connect(str(working)) as db:
            db.execute("insert into ufc_fighters values ('delta', 'D', 'Delta', null, null, null, null, null, 70, 70, null)")
        second = publish_snapshot(working, directory)
        metadata = client.get('/metadata').json()
        assert metadata['revision'] == second['revision']
        assert metadata['fighters'] == 4
        (directory / 'manifest.json').write_text(json.dumps(first))
        metadata = client.get('/metadata').json()
        assert metadata['revision'] == first['revision']
        assert metadata['fighters'] == 3


def test_snapshot_readers_are_isolated_from_a_separate_working_writer(tmp_path: Path, monkeypatch):
    import subprocess
    import sys

    working = tmp_path / 'working.duckdb'
    directory = tmp_path / 'published'
    seed_dashboard(working)
    snapshot = publish_snapshot(working, directory)
    script = """
import duckdb, sys
with duckdb.connect(sys.argv[1]) as db:
    db.execute("insert into ufc_events values ('new', 'New', '2099-01-02', 'City', '2025')")
    print('writing', flush=True)
    input()
"""
    from fastapi.testclient import TestClient
    from panoctagon.api.server import app
    monkeypatch.setenv('PANOCTAGON_API_SNAPSHOT_DIR', str(directory))
    process = subprocess.Popen([sys.executable, '-c', script, str(working)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == 'writing'
        with TestClient(app) as client:
            for _ in range(3):
                response = client.get('/metadata')
                assert response.status_code == 200
                assert response.json()['revision'] == snapshot['revision']
            with duckdb.connect(str(directory / snapshot['file']), read_only=True) as db:
                assert db.execute('select count(*) from ufc_events').fetchone()[0] == 2
    finally:
        process.communicate('\n', timeout=10)
    assert process.returncode == 0
