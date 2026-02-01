setup:
    uv run python -m panoctagon.utils.setup_db
    uv run dbt deps
    uv run dbt compile

refresh: setup
    DAGSTER_HOME="{{justfile_directory()}}/data/dagster" uv run dg launch --job refresh

dag:
    DAGSTER_HOME="{{justfile_directory()}}/data/dagster" uv run dg dev

db:
    duckdb -readonly data/panoctagon_orm.duckdb

dbw:
    duckdb data/panoctagon_orm.duckdb

viz:
    uv run python panoctagon/dashboard/main.py

check:
    uv run pyright .
    uv run ruff check --fix
    ruff check --select I --fix .
    uv run ruff format .
