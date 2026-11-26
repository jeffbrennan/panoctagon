"""API-only reader configuration and request-scoped snapshot selection."""
from contextvars import ContextVar
from dataclasses import dataclass
import json
import os
from pathlib import Path
import threading
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.pool import NullPool

DEFAULT_DUCKDB_MEMORY_LIMIT = '128MB'
DEFAULT_DUCKDB_THREADS = '2'


@dataclass(frozen=True)
class DatabaseRevision:
    path: Path
    revision: str
    published_at: str | None = None


_active: ContextVar[DatabaseRevision | None] = ContextVar('api_database_revision', default=None)
_engine_lock = threading.Lock()
_cached_engine_key: tuple[Any, ...] | None = None
_cached_engine: Engine | None = None
_runtime_warmed = False


def _duckdb_config() -> dict[str, Any]:
    config: dict[str, Any] = {}
    memory_limit = os.environ.get('PANOCTAGON_DUCKDB_MEMORY_LIMIT', DEFAULT_DUCKDB_MEMORY_LIMIT).strip()
    if memory_limit:
        config['memory_limit'] = memory_limit
    threads = os.environ.get('PANOCTAGON_DUCKDB_THREADS', DEFAULT_DUCKDB_THREADS).strip()
    if threads:
        config['threads'] = int(threads)
    return config


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


def warm_runtime() -> None:
    """Preload DuckDB's SQLAlchemy dialect and Python parameter type registry once at startup."""
    global _runtime_warmed
    if _runtime_warmed:
        return
    with _engine_lock:
        if _runtime_warmed:
            return
        engine = create_engine('duckdb:///:memory:', poolclass=NullPool)
        try:
            with engine.connect() as conn:
                conn.execute(text('select :probe'), {'probe': ''}).fetchall()
        finally:
            engine.dispose()
        _runtime_warmed = True


def dispose_cached_engines() -> None:
    """Dispose any cached read-only DuckDB engine."""
    global _cached_engine, _cached_engine_key
    with _engine_lock:
        engine = _cached_engine
        _cached_engine = None
        _cached_engine_key = None
    if engine is not None:
        engine.dispose()


def get_read_engine() -> Engine:
    """Return a revision- and file-stat-keyed read-only DuckDB engine."""
    global _cached_engine, _cached_engine_key
    path = current_revision().path
    try:
        st = path.stat()
    except FileNotFoundError:
        dispose_cached_engines()
        raise
    config = _duckdb_config()
    key = (
        str(path),
        st.st_dev,
        st.st_ino,
        st.st_mtime_ns,
        st.st_size,
        tuple(sorted(config.items())),
    )
    old_engine: Engine | None = None
    with _engine_lock:
        if _cached_engine is not None and _cached_engine_key == key:
            return _cached_engine
        old_engine = _cached_engine
        engine = create_engine(
            f'duckdb:///{path}',
            poolclass=NullPool,
            connect_args={'read_only': True},
        )
        if config:
            # duckdb-engine mutates connect_args['config'] in place (custom_user_agent),
            # which breaks concurrent DuckDB opens unless each connection gets a fresh copy.
            @event.listens_for(engine, 'do_connect')
            def _inject_fresh_config(_dialect, _conn_rec, _cargs, cparams, cfg=dict(config)):
                cparams['config'] = dict(cfg)
        _cached_engine = engine
        _cached_engine_key = key
    if old_engine is not None:
        old_engine.dispose()
    return engine
