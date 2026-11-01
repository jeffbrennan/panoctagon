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
