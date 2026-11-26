# Svelte performance hill-climbing plan

## Goal

Make dashboard transitions feel immediate: target **under 200 ms at p95** for
first-view transitions, chart readiness, parameter changes, and revisits on the
representative dataset and target devices. Treat this as a goal to work toward,
not a claim that the application already meets it. Measure desktop and a real
phone separately, with both a fresh browser and a warmed session. Also target
under 200 ms at p95 for relevant API requests after a fresh server process starts,
and for warm and post-publication requests.

The target covers time from an actual user action to the requested, correct
content being usable. For a chart, that means its data has been applied and a
frame containing the chart has rendered, not just that a canvas element exists
or a loading placeholder is visible. Measure the first meaningful frame; do not
wait for decorative animation to finish. For a revisit, include any scroll or
focus movement a user must perform to reach the chart. Record response latency
and transfer separately from rendering. Cold navigation includes any work that
must happen after the click; a hover or idle prefetch gets credit only in a
separately labeled scenario in which that opportunity actually occurred.

A 200 ms end-to-end goal cannot be guaranteed on arbitrary networks, devices, or
uncached data. Establish representative network and hardware profiles and report
failures and outliers rather than excluding them. Keep a separate stretch target
for a completely fresh browser with no opportunity to prefetch, and test cache
misses, revision changes and the first request after restart explicitly. Decide
whether the goal is achievable for each case from measurements on deployment
hardware; do not declare success solely from the local laptop.

## Starting evidence

The [November 1 release-gate report](release-gates/2026-11-01.md) provides the
baseline and raw samples. On that local dataset, warm-browser p95 was 406 ms for
the first fighter chart and 368 ms for the roster chart; the measured endpoint
was canvas visibility, so these numbers need a stronger rendered-frame check.
The roster API had a fresh-process p95 of 275 ms. Repeated navigation was
bimodal: early cycles took about 231–250 ms and later cycles about 881–884 ms,
with no repeat API requests in the investigation trace. These observations are
leads, not proof of their causes. Dash preloads charts and uses a random default
fighter, so its transition timings are not a controlled comparison.

## Measurement before optimization

1. Extend the existing [release-gate harness](../scripts/release-gates/) to time
   the same named fighter, division, year range, data revision and user action
   in each run. Record navigation start, interaction, view module ready, request
   start/end, data applied, chart modules ready, chart initialization, option
   application, first rendered data frame and interaction-ready time. Capture
   browser performance traces for the bimodal revisit case, including scrolling,
   layout, animation and long tasks. Distinguish actual rendering work from
   Playwright waiting for an element to become stable.
2. Define separate scenarios for: empty and populated Upcoming; first Fighters,
   Network and Roster visits; a long career; a sparse division; an all-years
   network; a fighter or filter change; a same-view revisit; and a return after a
   snapshot publication. For each, measure an immediate click with no prefetch,
   an intent-prefetch opportunity, and a warm revisit where applicable. Do not
   count a prefetched or previously initialized chart as a cold measurement.
3. Run at least 20 samples **per scenario and cache state**; use 50 or more for
   decisions when practical because 20 samples give a coarse p95. Record p50,
   p95, maximum, failures and raw samples. Separate a fresh browser from a fresh
   server process and from a warm server; note that restarting a process does
   not clear the OS file cache. Capture chart/canvas counts, transferred bytes,
   main-thread work, memory and CPU as well as time. Record the revision, data
   size, machine, runtime versions, browser, viewport and network conditions.
4. Use the same harness and dataset for an A/B comparison, alternating baseline
   and candidate runs where possible. Preserve raw traces and classify missing
   or failed results as failures. Re-run the November baseline with the stronger
   first-frame definition before treating the current numbers as comparable.

## Candidate experiments

Run one bounded experiment at a time. The ordering below prioritizes cheap,
reversible work around the measured transitions; keep only changes supported by
repeatable measurements.

1. **Explain revisit delays.** Instrument `Chart.svelte` visibility changes,
   ECharts animation pause/resume, resize and `setOption` calls alongside browser
   layout and scroll events. Compare a real pointer/keyboard navigation path
   with the harness's `scrollIntoViewIfNeeded` path. If animations, resizing or
   repeated option application cause the later 881 ms cycles, eliminate only
   redundant work or adjust the animation. Preserve pan/zoom, network focus,
   chart instances, and reduced-motion behavior. If the delay is test automation,
   correct the harness and retain the old and corrected measurements.
2. **Overlap code loading with user intent.** `App.svelte` currently prefetches
   a view module on navigation hover/focus, while `Chart.svelte` loads the chart
   runtime and family only after intersection. Experiment with starting the
   appropriate `loadChart` import on the same intent signal or after a view is
   requested, in parallel with its API request. Compare immediate click, keyboard
   focus then activation, touch, and idle-prefetch scenarios. Bound background
   work, respect data-saving preferences, and measure extra bytes, startup
   responsiveness, CPU and memory. Keep the original no-prefetch measurement.
3. **Overlap data and view loading.** A default fighter currently requires a
   search request followed by a profile request; the view module also loads
   before its local request effect runs. Test resolving a stable default from
   existing metadata or an additive server response, and starting an explicitly
   selected fighter's or division's request while its module loads. Do not bake
   in a fighter ID without a valid fallback. Avoid prefetching all analytics
   views, keep inactive views from polling, and measure whether speculative data
   requests improve actual clicks enough to justify the traffic.
4. **Reduce time to first chart frame.** Profile module parse/evaluation,
   ECharts initialization and `setOption` with representative long-career,
   roster and network datasets. Try a smaller chart-family import, avoiding
   duplicate initialization or redundant option creation, or rendering the
   first visible chart while deferring offscreen charts. Measure initial and
   total transfer, first-frame time, subsequent charts and retained memory.
   Do not remove data points, coverage gaps, axes, descriptions, or interactions
   merely to meet the target.
5. **Reduce cold roster and network work.** Profile the real SQL, connection
   setup, layout generation and serialization separately on a freshly published
   snapshot. If the cold roster remains above 200 ms, test query changes or
   precomputing revision-scoped results during publication/startup. A cache or
   prewarm must be keyed by the pinned snapshot revision and parameters, avoid
   a request stampede or a two-minute bucket rollover spike, and never serve a
   previous revision after publication or rollback. Measure startup/readiness,
   publication time, disk use and memory as well as request latency.
6. **Only then test heavier changes.** If profiles identify a CPU-bound option
   or layout calculation that still blocks interaction, compare moving that
   calculation to a worker or producing a revision-scoped artifact. Account for
   worker startup, serialization and transfer costs, cancellation, stale results,
   and the effect on small as well as large datasets. Do not add this complexity
   without a measured win.

## Experiment log

### Experiment 1: Revisit delays and redundant Network option application (kept — `d1bef52`)

- **Environment:** Apple M1 Pro, macOS, Node 26.13.0, Python 3.12.10, headless
  Chromium 1440×900, copied 2026-02-08 dataset, warm local server (`127.0.0.1:18751`).
  21 cycles per mode (1 initial load + 20 revisits), 0 errors/failures.
- **Root-cause findings (from trace `.scratch/release-gates/revisit-diagnostic.trace.json`
  and Playwright source inspection):**
  1. **Harness artifact (bimodal 231–250 ms vs 881–884 ms cycles):**
     `.view:not([hidden])` plays `animation: enter 160ms ease-out` (`translateY(5px)` → `0`).
     Playwright's `scrollIntoViewIfNeeded()` waits for `checkElementStates(["stable"])`
     using retry backoff `[0, 20, 100, 100, 500]` ms. When the animation steps
     between two consecutive rAFs, each chart view stalls for ~245 ms (~880 ms
     for all three chart views + Upcoming). Switching to native instant scrolling
     eliminates the stability wait; `prefers-reduced-motion: reduce` also drops
     `scrollMs` from ~245 ms to ~61 ms (its `0.01ms` duration still triggers one
     retry).
  2. **Application defect (42 `chart:network:set-option` calls in 21 visits):**
     `frontend/src/views/Network.svelte` bound `bind:clientWidth={graphWidth}`
     directly into the `$derived` ECharts `option`. Hiding the view sets
     `clientWidth` to `0` before `IntersectionObserver` sets `visible = false`,
     triggering a spurious `setOption` with `graphWidth = 0` on hide and another
     `setOption` on revisit (`0` → `1152`), adding ~52 ms to every Network revisit.
- **Change:** Guard `graphWidth` in `frontend/src/views/Network.svelte` so zero
  widths from hidden views are ignored while real viewport resizes still update
  node sizing. Add opt-in chart marks (`window.__chartPerformanceGate`) in
  `frontend/src/lib/Chart.svelte`, comparison modes in
  `scripts/release-gates/revisit-diagnostic.cjs`, and a fresh-context
  first-frame harness in `scripts/release-gates/transition-benchmark.cjs`.
- **Controlled A/B results (20 revisits per mode, `GATE_TRACE=0`, 0 errors):**

| Mode / View | Baseline p50 / p95 / max (ms) | Candidate p50 / p95 / max (ms) | `network:set-option` count (21 visits) |
| --- | ---: | ---: | ---: |
| `playwright-scroll` Fighters | 298.7 / 300.1 / 301.1 | 299.0 / 300.5 / 301.1 | — |
| `playwright-scroll` Network | 298.8 / 299.8 / 300.7 | 298.8 / 300.0 / 300.5 | 42 → 1 |
| `playwright-scroll` Roster | 298.8 / 300.4 / 315.1 | 298.6 / 300.0 / 300.6 | — |
| `user-pointer` Fighters | 47.6 / 48.8 / 49.6 | 47.6 / 49.1 / 49.3 | — |
| `user-pointer` Network | **99.9 / 100.2 / 100.3** | **49.0 / 50.9 / 51.4** | **42 → 1** |
| `user-pointer` Roster | 48.1 / 49.1 / 49.9 | 48.5 / 49.5 / 49.8 | — |
| `user-keyboard` Fighters | 12.7 / 14.4 / 18.6 | 13.1 / 14.5 / 18.9 | — |
| `user-keyboard` Network | **66.8 / 68.4 / 68.7** | **16.2 / 16.5 / 16.6** | **42 → 1** |
| `user-keyboard` Roster | 15.0 / 15.3 / 30.6 | 15.5 / 15.8 / 15.8 | — |
| `reduced-motion` Network | 115.1 / 115.9 / 116.5 | 115.9 / 116.9 / 117.6 | 42 → 1 |

- **Decision:** Kept. All real-user revisits are now well under 200 ms p95
  (14–16 ms keyboard, 49–51 ms pointer including ~36 ms Playwright click check).
  Artifacts: `.scratch/release-gates/revisit-{baseline,exp1}-*.json`.
  Validation: `svelte-check` (0 errors), Vitest (13/13), Playwright desktop +
  mobile + axe (36/36), Python dashboard/web/snapshot/cutover tests (17/17).

### Experiment 2: Overlap chart-family loading with view intent and activation (kept — `a134352`)

- **Hypothesis:** Preloading the view's ECharts family on nav hover/focus (when
  `navigator.connection.saveData` is unset) and queueing `preloadChart(family)`
  right after view mount in `show()` lets chart module download/parse overlap
  with hover dwell and API requests instead of waiting for `IntersectionObserver`.
- **Change:** Memoize `loadChart` with failure eviction and add `preloadChart`
  in `frontend/src/lib/chartLoader.ts`; call `preloadChart` in `prefetch()`
  (respecting `saveData`) and via `queueMicrotask` after mount in `show()` in
  `frontend/src/App.svelte`.
- **Controlled A/B results (`transition-benchmark.cjs`, 20 fresh contexts per
  scenario, warm local server, 0 errors/failures):**

| Scenario / Metric | Baseline (`d1bef52`) p50 / p95 / max (ms) | Candidate p50 / p95 / max (ms) |
| --- | ---: | ---: |
| `desktop-immediate` Upcoming | 60.7 / 63.4 / 67.2 | 60.3 / 62.9 / 67.1 |
| `desktop-immediate` Fighter data | 92.6 / 93.7 / 94.4 | 114.0 / 115.7 / 116.2 |
| `desktop-immediate` Fighter chart | **147.2 / 149.7 / 158.3** | **131.0 / 132.8 / 143.7** |
| `desktop-immediate` Network chart | 67.3 / 75.7 / 77.1 | 67.5 / 83.6 / 84.3 |
| `desktop-immediate` Roster chart | 84.1 / 100.8 / 101.8 | 83.8 / 99.4 / 100.6 |
| `desktop-hover` (150 ms) Fighter chart | **146.3 / 148.6 / 154.5** | **113.4 / 114.6 / 132.2** |
| `desktop-hover` (150 ms) Network chart | **64.9 / 95.8 / 96.7** | **65.3 / 83.0 / 113.9** |
| `desktop-hover` (150 ms) Roster chart | 82.6 / 99.0 / 195.1 | 80.7 / 98.1 / 147.1 |
| `mobile-touch` (390×844) Fighter chart | **231.2 / 248.4 / 261.6** | **229.3 / 231.1 / 243.4** |
| `mobile-touch` (390×844) Roster chart | **166.5 / 167.6 / 167.8** | **150.9 / 166.7 / 167.0** |

- **Cost and trade-offs:** Upcoming initial transfer changed from 26,601 to
  27,032 bytes (+431 bytes); total transfer across all views was unchanged
  (377,168 → 377,250 bytes). Zero ECharts chunks load on Upcoming. On
  `desktop-immediate`, parsing ECharts during the fighter API wait shifts
  `fighterDataMs` from 93.7 → 115.7 ms while cutting total `fighterChartMs`
  from 149.7 → 132.8 ms (-17 ms); on `desktop-hover`, parse completes during
  hover dwell (-34 ms on `fighterChartMs`). On `mobile-touch`, `modules-start`
  → `modules-ready` dropped from 33.2 ms to 0.1 ms, cutting p95 by 17 ms,
  leaving the two-step default-fighter API waterfall as the remaining mobile
  bottleneck above 200 ms.
- **Decision:** Kept. Artifacts: `.scratch/release-gates/transition-{baseline,exp2b}-*.json`.
  Validation: `svelte-check` (0 errors), Vitest (13/13), Playwright desktop +
  mobile + axe (36/36).

### Experiment 3: Eliminate default-fighter waterfall, cache fighter bio/record, and overlap view data with module load (kept)

- **Hypothesis:** Resolving `default_fighter_uid` inside cached `DashboardMetadata`,
  caching fighter bio/record in `fighter_analytics()` (instead of running uncached
  `get_fighter_detail()` and discarding `recent_fights`), and warming the active
  view's first API request in parallel with `loaders[next]()` in `App.svelte`
  removes the two-step fighter search waterfall and cuts both data and chart readiness.
- **Change:**
  - `panoctagon/api/models.py` & `panoctagon/api/analytics.py`: add additive
    `default_fighter_uid: Optional[str] = None` to `DashboardMetadata` (prefers
    Max Holloway, else most completed fights, else first fighter); replace
    uncached `get_fighter_detail()` inside `fighter_analytics()` with a single
    revision-pinned cached `rows()` query for bio + record.
  - `frontend/src/lib/api.ts`: add revision-safe `warmApi(path)` with in-flight
    deduplication (`inflight` map cleared on `invalidateCache()`), honoring
    `AbortSignal` and `bypass`.
  - `frontend/src/views/Fighters.svelte` & `frontend/src/App.svelte`: read
    `metadata?.default_fighter_uid` (falling back to `/fighter?name=Max%20Holloway&limit=1`
    when absent) and call `warmViewData(next)` on first view load (`!pages[next]`)
    only after the user navigates to `next` (no speculative prefetch of hidden views).
- **Controlled A/B results (`transition-benchmark.cjs`, 20 fresh contexts per
  scenario, warm local server, 0 errors/failures):**

| Scenario / Metric | Baseline (`a134352`) p50 / p95 / max (ms) | Candidate p50 / p95 / max (ms) |
| --- | ---: | ---: |
| `desktop-immediate` Fighter data | **114.0 / 115.7 / 116.2** | **34.7 / 35.8 / 48.3** |
| `desktop-immediate` Fighter chart | **131.0 / 132.8 / 143.7** | **112.1 / 130.4 / 130.4** |
| `desktop-immediate` Roster data | **43.6 / 70.0 / 90.7** | **38.6 / 43.4 / 54.4** |
| `desktop-immediate` Roster chart | **83.8 / 99.4 / 100.6** | **84.0 / 85.4 / 100.0** |
| `desktop-hover` Fighter data | **95.6 / 99.3 / 113.8** | **37.9 / 38.8 / 72.7** |
| `desktop-hover` Fighter chart | **113.4 / 114.6 / 132.2** | **96.0 / 97.1 / 97.5** |
| `desktop-hover` Network chart | 65.3 / 83.0 / 113.9 | 64.7 / 80.3 / 81.9 |
| `desktop-hover` Roster chart | 80.7 / 98.1 / 147.1 | 80.6 / 96.9 / 97.1 |
| `mobile-touch` Fighter chart | **229.3 / 231.1 / 243.4** | **213.6 / 230.5 / 230.7** |
| `mobile-touch` Network chart | **150.7 / 165.8 / 167.0** | **150.5 / 151.2 / 151.3** |
| `mobile-touch` Roster data | **115.4 / 146.1 / 147.9** | **115.7 / 117.2 / 117.6** |
| `mobile-touch` Roster chart | 150.9 / 166.7 / 167.0 | 165.5 / 166.4 / 167.1 |

- **Cost and trade-offs:** Upcoming transfer changed from 27,032 to 27,298 bytes
  (+266 bytes for `warmApi` + `default_fighter_uid` field); total transfer across
  all views changed from 377,250 to 377,402 bytes (+152 bytes). Zero extra
  requests occur on Upcoming or on hover; `warmViewData` fires only on actual
  activation of an unloaded view. On desktop, `fighterDataMs` p95 dropped by
  80 ms (`desktop-immediate`) and 60 ms (`desktop-hover`), bringing `desktop-hover`
  `fighterChartMs` p95 under 100 ms (97.1 ms). On `mobile-touch`, Playwright's
  `link.tap()` actionability check accounts for ~90 ms of the measured window
  and `set-option` → `data-frame` still takes ~54 ms (44 ms on desktop) because
  of ECharts `lazyUpdate: true` + initial paint scheduling (next target: Experiment 4).
- **Decision:** Kept. Artifacts: `.scratch/release-gates/transition-{exp2b,exp3}-*.json`.
  Validation: Python suite (18/18), `svelte-check` (0 errors), Vitest (14/14),
  Playwright desktop + mobile + axe (36/36), Playwright integration (2/2).

## Keep-or-revert loop

For each experiment, record the hypothesis, exact change and commit, baseline
and candidate p50/p95/max, sample count, errors, cold/warm state, transferred
bytes, memory and trace links. Keep a change when it produces a repeatable
improvement in the intended scenario without a material regression in other
scenarios or correctness; otherwise revert it and record what was learned. A
change that only moves work earlier must report that work and its costs. Repeat
the highest-impact remaining experiment until the relevant p95s are under
200 ms or measurements identify a concrete constraint requiring a revised target.

Every candidate must retain snapshot freshness and revision isolation, request
cancellation, explicit retry behavior, visible failure states, chart and selection
retention, keyboard access, reduced motion, and correct treatment of missing
statistics. Run focused unit and integration tests plus the existing browser and
accessibility checks after each retained change. Recheck the release image and
representative phone/network conditions before calling the performance gate passed.
