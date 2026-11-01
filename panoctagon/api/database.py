"""Database configuration for API readers; ingestion always uses the working database."""
import os
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import NullPool


def get_read_engine() -> Engine:
    default = Path(__file__).parents[2] / 'data' / 'panoctagon_orm.duckdb'
    path = Path(os.environ.get('PANOCTAGON_API_DATABASE', default)).resolve()
    return create_engine(f'duckdb:///{path}', poolclass=NullPool, connect_args={'read_only': True})
