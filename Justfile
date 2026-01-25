refresh:
    uv run dg launch --assets ufc_events+

dag:
    uv run dg dev

db:
    duckdb data/panoctagon_orm.db -ui

check:
    uv run pyright .
    uv run ruff check --fix
    uv run ruff format .
