#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export IMAGE_TAG="${IMAGE_TAG:-latest}"
COMPOSE=(docker compose -f docker-compose.yaml -f docker-compose.svelte.yaml -f docker-compose.prod.yaml)

echo "==> Pulling prebuilt images (tag: ${IMAGE_TAG})"
"${COMPOSE[@]}" pull

if [ ! -f data/api_snapshots/manifest.json ] && [ -f data/panoctagon_orm.duckdb ]; then
  echo "==> First-time snapshot bootstrap: draining running containers..."
  docker compose -f docker-compose.yaml stop || true
  echo "==> Publishing initial read-only DuckDB snapshot..."
  "${COMPOSE[@]}" run --rm --no-deps --entrypoint /panoctagon/.venv/bin/python panoctagon_backend -c \
    "from pathlib import Path; from panoctagon.api.snapshots import publish_snapshot; print(publish_snapshot(Path('/panoctagon/data/panoctagon_orm.duckdb'), Path('/panoctagon/data/api_snapshots')))"
fi

echo "==> Starting updated services"
"${COMPOSE[@]}" up -d --no-build --remove-orphans

echo "==> Waiting for panoctagon_frontend /readyz"
ready=0
for _ in $(seq 1 30); do
  if "${COMPOSE[@]}" exec -T panoctagon_frontend /panoctagon/.venv/bin/python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8050/readyz', timeout=5)" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done

if [ "$ready" -ne 1 ]; then
  echo "ERROR: panoctagon_frontend failed readiness check" >&2
  "${COMPOSE[@]}" logs --tail=60 panoctagon_frontend >&2 || true
  exit 1
fi

echo "==> Cleaning up old unused images (>7 days)"
docker image prune -f --filter "until=168h" >/dev/null 2>&1 || true

echo "==> Deploy complete (${IMAGE_TAG})"
"${COMPOSE[@]}" ps
