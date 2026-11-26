# Panoctagon web frontend

Svelte 5 + TypeScript + ECharts dashboard for panoctagon, backed by FastAPI and DuckDB.

## Run locally

From the repository root, start the API against your local `data/panoctagon_orm.duckdb`:

```sh
uv run --python 3.12 uvicorn panoctagon.api.server:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/api` to the local FastAPI server so the browser uses a single origin. To point at another API, set `API_PROXY_TARGET` in a local `.env` file (without an `/api` prefix).

Headshots are served from `data/raw/ufc/fighter_headshots/` (missing images fall back to initials). If your local database snapshot has no future cards, the Upcoming view shows an empty state while Fighters, Network, and Roster work normally.

For a production-style single-process run, use `just webpreview` from the repo root and open <http://127.0.0.1:8080>. FastAPI serves the built frontend and `/api` together with gzip and immutable caching for hashed assets.

## Validate

```sh
npm run check
npm test
npm run build
npx playwright install chromium firefox webkit
npm run test:ui
```

The Playwright suite uses deterministic API fixtures and covers desktop/mobile navigation, search, matchup filtering, chart loading, pagination, retries, accessibility, and overflow across 320, 390, 768, and 1440px viewports. Reports and traces go to `.scratch/`.

Python API and server tests run against a temporary DuckDB database:

```sh
uv run --python 3.12 pytest tests/test_dashboard_api.py tests/test_web_server.py
```

## Notes

- The initial Upcoming view does not load ECharts or fetch analytics for hidden views.
- Views load on first navigation and preserve their controls and chart instances when revisiting.
- Chart code loads near the viewport, and `ResizeObserver` batches resizes into animation frames.
- Network graph coordinates are computed on the server rather than running a force simulation in the browser.
- API responses use a bounded two-minute in-memory cache; search requests are debounced and superseded requests are cancelled.
- ECharts imports only the chart types and components actually used, and respects `prefers-reduced-motion`.
- Routes use `?view=fighters`, `?view=network`, and `?view=roster` (with `?view=fighters&fighter=<uid>` for fighter deep links) so bookmarks and back/forward work without server-side rewrites.
