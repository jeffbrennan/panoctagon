# panoctagon

UFC fight data aggregation, analysis, and visualization

## Local frontend rewrite

A Svelte + ECharts frontend is available in [`frontend/`](frontend/README.md). Run
`just api` and `just web` in separate terminals, then open <http://127.0.0.1:5173>.
It uses the existing local DuckDB data through FastAPI. The production dashboard and
Docker configuration still use Dash while the rewrite is evaluated locally.

Live at [panoctagon.jeffbrennan.dev](https://panoctagon.jeffbrennan.dev)

## Site

The dashboard has four main views:

### Upcoming
Shows upcoming UFC events with fighter matchup comparisons, physical stats, records, and betting odds.

 ![upcoming](docs/upcoming.png)

### Fighters
Individual fighter profiles with career stats, fight history, and performance breakdowns.

 ![fighters](docs/fighters.png)

### Network
Visual graph of fighter matchup connections.

 ![network](docs/network.png)

### Roster
Searchable roster with division filtering and stat comparisons.

 ![roster](docs/roster.png)

## API

Available at `/api`. Full docs at `/api/docs`.

| Endpoint | Description |
| --- | --- |
| `GET /fighter` | Search fighters by name or division |
| `GET /fighter/{id}` | Fighter bio, record, and recent fights |
| `GET /fighter/{id}/stats` | Fighter statistics |
| `GET /fighter/{id}/fights` | Fight history |
| `GET /events` | List events |
| `GET /event/{id}` | Event details and fight card |
| `GET /fight/{id}` | Fight details with round-by-round stats |
| `GET /rankings` | Leaderboard by division |
| `GET /roster` | UFC roster with filters |
| `GET /upcoming` | Upcoming events and matchups |
| `GET /divisions` | All divisions |

## CLI

The `panoctagon` CLI provides terminal access to the same data.

```
panoctagon upcoming
panoctagon fighter "Max Holloway"
panoctagon compare "Max Holloway" "Ilia Topuria"
panoctagon leaderboard
panoctagon event
panoctagon roster
```

## Pipeline

Data is scraped, parsed, and transformed using Dagster and dbt.

 ![pipeline](docs/pipeline.jpg)

## Stack

Python, FastAPI, Dash, DuckDB, Dagster, dbt

## Sources

- [ufcstats.com](http://ufcstats.com) - fight stats and decisions
- [bestfightodds.com](https://www.bestfightodds.com) - betting odds

### Svelte dashboard checks

With Python 3.12.12, Node 26.13.0 and uv installed, run `uv sync --frozen`,
`cd frontend && npm ci`, then `npm run check`, `npm test`, and `npm run build`.
Install browsers with `npx playwright install --with-deps chromium firefox webkit`.
`npx playwright test` runs the fixture-based interaction suite; `npx playwright
test -c playwright.integration.config.ts` runs the built application against an
isolated database under `.scratch/integration`. The integration server requires
port 8765 and never opens the working ingestion database.

### API snapshots

The refresh job publishes a checkpointed copy to `data/api_snapshots` only after
its upstream assets and blocking checks pass. The existing blocking check still
requires at least one upcoming fight: an empty calendar is valid for readers,
but ingestion currently treats it as a failed refresh pending an operational
policy change. Dagster is configured to run one job at a time and publication
uses the `duckdb_write` pool. Manual production writers must stop and drain
Dagster runs and all other working-database writers before writing or publishing;
they must maintain that boundary until checkpoint, copy, and validation finish.
Set `PANOCTAGON_API_SNAPSHOT_DIR` on API readers to use the manifest. Bootstrap
and validate a snapshot before enabling this setting. Keep old snapshot files
until readers have drained; cleanup is a controlled maintenance action.
