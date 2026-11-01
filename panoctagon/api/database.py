"""API-only reader configuration and request-scoped snapshot selection."""
from contextvars import ContextVar
from dataclasses import dataclass
import json
import os
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import NullPool


@dataclass(frozen=True)
class DatabaseRevision:
    path: Path
    revision: str
    published_at: str | None = None


_active: ContextVar[DatabaseRevision | None] = ContextVar('api_database_revision', default=None)


def resolve_revision() -> DatabaseRevision:
    snapshot_dir = os.environ.get('PANOCTAGON_API_SNAPSHOT_DIR')
    if snapshot_dir:
        directory = Path(snapshot_dir).resolve()
        manifest = json.loads((directory / 'manifest.json').read_text())
        filename = manifest['file']
        if not isinstance(filename, str) or Path(filename).name != filename or not filename.endswith('.duckdb'):
            raise ValueError('Invalid snapshot filename')
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        return DatabaseRevision(path, manifest['revision'], manifest['published_at'])
    default = Path(__file__).parents[2] / 'data' / 'panoctagon_orm.duckdb'
    path = Path(os.environ.get('PANOCTAGON_API_DATABASE', default)).resolve()
    return DatabaseRevision(path, str(path))


def current_revision() -> DatabaseRevision:
    return _active.get() or resolve_revision()


def get_read_engine() -> Engine:
    return create_engine(f'duckdb:///{current_revision().path}', poolclass=NullPool,
                         connect_args={'read_only': True})
