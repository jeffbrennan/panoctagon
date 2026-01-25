refresh:
    uv run dg launch --assets ufc_events+

dag:
    uv run dg dev


check:
    uv run pyright .
    uv run ruff check --fix
    uv run ruff format .
