# Svelte cutover preparation

This is an opt-in configuration; do not switch traffic until the parity,
performance, concurrent-read and rollback gates in the implementation plan are
complete. See the [local gate report](release-gates/2026-11-01.md) for evidence
and remaining work. Record the exact immutable image digests and Compose configuration for
both the prior Dash/API services and the new service in the deployment record.

1. Inventory consumers of `panoctagon_api:8000` outside this repository. A
   repository search found only its Compose definition; this does not establish
   that external consumers do not exist. The opt-in configuration keeps that
   service internal and makes it read snapshots. Build and deploy the updated
   API image as well; an older API image does not understand snapshot settings. Verify each consumer before
   retiring it.
2. Deploy the publisher configuration, ensure only one Dagster run can execute,
   and finish a successful full refresh. Check `data/api_snapshots/manifest.json`
   and retain the file named there. The blocking zero-upcoming policy remains
   active. Do not publish manually unless all writers and runs are stopped and
   drained for the entire checkpoint, copy, and validation sequence.
3. Build and record the immutable Svelte image digest. Retain the previously
   deployed Dash and API images and their exact configuration. Rehearse with
   `docker compose -f docker-compose.yaml -f docker-compose.svelte.yaml config`.
   The opt-in configuration disables Traefik discovery for the standalone API;
   the existing frontend host router forwards both `/` and `/api` unchanged
   to port 8050. The Dagster path router is unchanged. Snapshot and headshot
   mounts are read-only in both readers.
4. In a staging environment, verify `/healthz`, `/readyz`, `/api/metadata`,
   `/api/docs`, all four views, fighter links and headshots, and confirm proxy
   requests contain `/api` exactly once. Confirm the running manifest revision
   matches metadata. Verify Dagster remains reachable at `/dagster`.
5. After recording gate results and obtaining the deployment decision, apply
   the exact reviewed configuration and monitor a full ingestion/publication
   cycle. Keep old snapshots and images for rollback.

## Rollback

Record and rehearse the exact previous image digests and proxy configuration.
If old Dash or API images read the working DuckDB file, first pause scheduled
and manual ingestion and drain all writers. Restore the previous images and
router configuration only after writers have stopped. Keep ingestion paused
until readers are moved to a safe configuration or drained. This trades data
freshness for reader availability; resuming writes while old readers are active
is unsafe. A snapshot-only rollback can instead atomically repoint the manifest
to a retained validated revision; verify metadata and cache isolation afterward.
