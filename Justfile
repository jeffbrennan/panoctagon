refresh:
    uv run dg launch --assets promotions+

dag:
    uv run dg dev

db:
    duckdb data/panoctagon_orm.db -ui

check:
    uv run pyright .
    uv run ruff check --fix
    ruff check --select I --fix .
    uv run ruff format .
