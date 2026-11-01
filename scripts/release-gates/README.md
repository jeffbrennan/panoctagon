# Local release-gate harness

These scripts reproduce the local sampling in [the report](../../docs/release-gates/2026-11-01.md).
They are not production deployment scripts. Run from the repository root with
`.venv` and `frontend/node_modules` installed. The browser harness assumes the
specific 2026-02-08 dataset documented in that report; other datasets need
adjusted expected names and counts. Ports 18750–18758 must be free. The browser
scripts require a Playwright Chromium install.

Create disposable copies only after confirming no writer holds the local working
file and no WAL remains. For example, on macOS:

```sh
mkdir -p .scratch/release-gates/baseline/data .scratch/release-gates/data
git archive 74c0bb5 | tar -x -C .scratch/release-gates/baseline
cp -c data/panoctagon_orm.duckdb .scratch/release-gates/baseline/data/panoctagon_orm.duckdb
cp -c data/panoctagon_orm.duckdb .scratch/release-gates/data/panoctagon_orm.duckdb
mkdir -p .scratch/release-gates/baseline/data/raw/ufc
ln -s "$PWD/data/raw/ufc/fighter_headshots" .scratch/release-gates/baseline/data/raw/ufc/fighter_headshots
npm --prefix frontend run build
```

Start these in separate terminals from the repository root. The first runs from
inside the archive so all Dash readers use its copied database. The second uses
an API-only environment override; neither process writes the original database.

```sh
(cd .scratch/release-gates/baseline && PYTHONPATH=. ../../../.venv/bin/gunicorn --bind 127.0.0.1:18750 --workers 2 --timeout 120 panoctagon.dashboard.main:server)
PANOCTAGON_API_DATABASE="$PWD/.scratch/release-gates/data/panoctagon_orm.duckdb" .venv/bin/uvicorn panoctagon.web.server:app --host 127.0.0.1 --port 18751 --no-access-log
```

Then run:

```sh
node scripts/release-gates/browser-benchmark.cjs
.venv/bin/python scripts/release-gates/api-benchmark.py
.venv/bin/python scripts/release-gates/cold-api-benchmark.py
node scripts/release-gates/repeated-navigation.cjs
node scripts/release-gates/trace-transitions.cjs
PYTHONPATH="$PWD/.scratch/release-gates/baseline" .venv/bin/python scripts/release-gates/dash-network-benchmark.py
```

The browser benchmark defaults to 20 samples per implementation and writes
`.scratch/release-gates/bench.json`; `GATE_SAMPLES` and `GATE_OUTPUT` override
those settings. Restart both servers before a first-browser measurement, then
set `GATE_SAMPLES=1` and use a separate output path. The process-cold API script
starts and stops 20 readers on port 18758, without clearing the operating-system
file cache. Avoid other demanding work during measurements. All timing methods
and their limitations are described in the report.

For the proxy rehearsal, also run the archived API on 18752 and the echo stub on
18753. It returns the incoming path and stands in for Dagster; it is not a
Dagster validation. Start Traefik with its file provider restricted to an isolated
configuration directory and bind its test port to localhost:

```sh
(cd .scratch/release-gates/baseline && PYTHONPATH=. ../../../.venv/bin/uvicorn panoctagon.api.server:app --host 127.0.0.1 --port 18752 --no-access-log)
.venv/bin/python scripts/release-gates/mock-dagster.py
mkdir -p .scratch/release-gates/traefik
cp scripts/release-gates/traefik/*.yml .scratch/release-gates/traefik/
cp .scratch/release-gates/traefik/legacy.yml .scratch/release-gates/traefik/active.yml
docker run -d --name panoctagon-gate-traefik -p 127.0.0.1:18754:8080 --mount "type=bind,src=$PWD/.scratch/release-gates/traefik,dst=/config,readonly" traefik:v3.6 --entrypoints.web.address=:8080 --providers.file.filename=/config/active.yml --providers.file.watch=true
.venv/bin/python scripts/release-gates/proxy-rehearsal.py
docker rm -f panoctagon-gate-traefik
```

The snapshot rollback script additionally requires a snapshot-backed Svelte
reader on port 18757, two deliberately different snapshots and a
`.scratch/release-gates/snapshot-revisions.json` array holding their manifests.
It is tailored to the recorded 2,637/2,638-fighter fixture and must be adapted
for other data. Never repoint a production manifest for this exercise.
