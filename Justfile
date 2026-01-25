refresh:
    uv run dg launch --job refresh

dag:
    uv run dg dev

db:
    duckdb -readonly data/panoctagon_orm.duckdb

dbw:
    duckdb data/panoctagon_orm.duckdb

viz:
    uv run python panoctagon/dashboard.py

check:
    uv run pyright .
    uv run ruff check --fix
    ruff check --select I --fix .
    uv run ruff format .
