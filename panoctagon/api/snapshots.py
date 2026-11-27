"""Immutable DuckDB snapshot publication.

The caller must hold the ingestion-wide writer serialization boundary throughout
checkpoint, copy and validation. A process-local lock is not sufficient.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb

REQUIRED_TABLES = ('ufc_events', 'ufc_fighters', 'ufc_fights', 'ufc_fight_stats',
                   'bfo_ufc_link', 'bfo_parsed_odds')


def publish_snapshot(working: Path, directory: Path) -> dict[str, str]:
    """Publish a checkpointed copy after validation, retaining all older files."""
    directory.mkdir(parents=True, exist_ok=True)
    revision = uuid.uuid4().hex
    filename = f'{revision}.duckdb'
    candidate = directory / filename
    temporary_manifest = directory / f'.manifest-{revision}.tmp'
    try:
        # The caller must have drained and closed all other working DB handles.
        with duckdb.connect(str(working)) as db:
            db.execute('CHECKPOINT')
        if Path(f'{working}.wal').exists():
            raise RuntimeError('Working database still has a WAL after checkpoint')
        with working.open('rb') as source, candidate.open('xb') as target:
            shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())
        with duckdb.connect(str(candidate), read_only=True) as db:
            for table in REQUIRED_TABLES:
                db.execute(f'SELECT * FROM {table} LIMIT 0')
        manifest = {'file': filename, 'revision': revision,
                    'published_at': datetime.now(timezone.utc).isoformat()}
        with temporary_manifest.open('x') as handle:
            json.dump(manifest, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_manifest, directory / 'manifest.json')
        return manifest
    except BaseException:
        candidate.unlink(missing_ok=True)
        temporary_manifest.unlink(missing_ok=True)
        raise
