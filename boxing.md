# Boxing parity plan

Goal: bring the boxing pipeline toward the UFC implementation's operational and data-consumption parity without copying UFC-only fields that FightNights cannot provide.

## Milestone 1: Make boxing operationally reachable

- [ ] Add `panoctagon/boxing/app.py` to aggregate scrape and parse Typer commands.
- [ ] Register the boxing app in `panoctagon/admin.py`.
- [ ] Expose and test the commands below:
  - `admin boxing scrape events`
  - `admin boxing scrape event-pages`
  - `admin boxing scrape fighters`
  - `admin boxing parse events`
  - `admin boxing parse fighters`
- [ ] Add CLI smoke tests without performing network requests or database writes.

## Milestone 2: Normalize completed boxing fights

- [x] Add completed-event/fight discovery and refresh behavior.
- [x] Populate `BoxingFight` outcomes, decisions, and decision rounds.
- [x] Reconcile `BoxingFightHistory` with stable `BoxingFight`/`match_uid` identities.
- [x] Replace event bouts atomically so removed bouts do not remain stale.
- [x] Extract event titles instead of persisting blank titles.

## Milestone 3: Match supported data depth

- [ ] Determine which boxing round-level statistics FightNights exposes.
- [ ] Add boxing stats models, parsers, and writers only for source-supported fields.
- [ ] Decide separately whether boxing needs odds, bios, or headshots; these are UFC-specific features, not automatic parity requirements.

## Milestone 4: Wire production orchestration and consumers

- [ ] Add boxing Dagster assets and dependencies.
- [ ] Add boxing dbt sources/staging models where transformations are needed.
- [ ] Add boxing API query/response paths.
- [ ] Add boxing dashboard views if boxing belongs in the existing UI.

## Milestone 5: Harden and validate

- [ ] Make force and refresh semantics reliable.
- [ ] Report scraper failures and remove invalid files.
- [ ] Add malformed-page, writer, timestamp, idempotence, and orchestration tests.
- [ ] Repair or fixture-gate unrelated UFC tests so the full suite is a meaningful gate.
