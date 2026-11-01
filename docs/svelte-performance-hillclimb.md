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
