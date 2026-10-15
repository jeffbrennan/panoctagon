# Panoctagon web frontend

Local Svelte 5 + TypeScript + ECharts replacement for the Dash dashboard. The Python scraping, Dagster, dbt, DuckDB, and existing API remain in place. The production Docker configuration still starts Dash; nothing in this directory deploys automatically.

## Run locally

From the repository root, start the API against your existing `data/panoctagon_orm.duckdb`:

```sh
uv run uvicorn panoctagon.api.server:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/api` to the local FastAPI server, so the browser uses a single origin. To use another API, set `API_PROXY_TARGET` in a local `.env` file. This target should expose endpoints at its root, without an `/api` prefix.

Headshots are served from `data/raw/ufc/fighter_headshots/`. Missing images display fighter initials. An old database can legitimately show no upcoming events; historical fighter, network, and roster views remain available.

## Validate

```sh
npm run check
npm test
npm run build
npx playwright install chromium
npm run test:ui
```

The browser suite uses deterministic API fixtures and covers desktop/mobile navigation, search, matchup filtering, chart loading, pagination, retries, and horizontal overflow at 320, 390, 768, and 1440 pixels. Reports, traces, and screenshots are written to the repository's ignored `.scratch/` directory. Python analytics tests use their own temporary DuckDB database:

```sh
uv run pytest tests/test_dashboard_api.py
```

Use `npm run preview` to serve the production build at <http://127.0.0.1:4173> with the same API proxy.

For a production-style local run with one Python process, run `just webpreview` from
the repository root and open <http://127.0.0.1:8080>. FastAPI serves the built frontend
and `/api` together, with gzip and immutable caching for hashed assets. Node is only
needed to build the frontend. This does not change or start the production Docker services.

## Performance choices

- The initial Upcoming view does not import ECharts or fetch analytics for hidden views.
- Views load on first navigation. Visited views retain their controls and chart instances.
- Chart code loads near the viewport. ResizeObserver batches chart resizing into animation frames.
- Network coordinates are calculated on the server; the browser does not run a force simulation.
- Successful API responses have a bounded, two-minute in-memory cache. Search requests are debounced and obsolete requests are cancelled.
- ECharts imports only the chart types/components in use. Updates retain instances and animate data changes; system reduced-motion preferences disable animations.
- Headshots use native lazy loading and browser caching, rather than embedded base64 payloads.

Routes use `?view=fighters`, `?view=network`, and `?view=roster`; a fighter profile can be linked with `?view=fighters&fighter=<uid>`. Browser back/forward and opening links in new tabs work without a server-side routing fallback.
