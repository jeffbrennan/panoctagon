// Measures first-visit chart readiness (rendered frame, not just canvas visibility)
// and parameter-change transitions without Playwright's scrollIntoViewIfNeeded stability backoff.
const { chromium } = require('../../frontend/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const { performance } = require('perf_hooks');

const samples = Number(process.env.GATE_SAMPLES || 20);
const output = process.env.GATE_OUTPUT || '.scratch/release-gates/transition-benchmark.json';
const url = process.env.GATE_URL || 'http://127.0.0.1:18751';
const scenario = process.env.GATE_SCENARIO || 'desktop-immediate';
const validScenarios = new Set(['desktop-immediate', 'desktop-hover', 'mobile-touch']);
if (!Number.isInteger(samples) || samples < 1) throw new Error('GATE_SAMPLES must be a positive integer');
if (!validScenarios.has(scenario)) throw new Error(`GATE_SCENARIO must be one of: ${[...validScenarios].join(', ')}`);

function percentile(values, p) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1)];
}

function summarize(values) {
  const clean = values.filter((v) => typeof v === 'number' && Number.isFinite(v));
  if (!clean.length) return null;
  return {
    n: clean.length,
    p50: Number(percentile(clean, 50).toFixed(2)),
    p95: Number(percentile(clean, 95).toFixed(2)),
    max: Number(Math.max(...clean).toFixed(2)),
  };
}

async function scrollChartInstant(chart) {
  await chart.evaluate((el) => {
    const r = el.getBoundingClientRect();
    if (r.top < 0 || r.bottom > window.innerHeight) {
      el.scrollIntoView({ behavior: 'instant', block: 'nearest' });
    }
  });
}

async function waitForChartFrame(page, chart, timeout = 120000) {
  await chart.waitFor({ state: 'visible', timeout });
  await scrollChartInstant(chart);
  await chart.locator('canvas').first().waitFor({ state: 'visible', timeout });
  const handle = await chart.elementHandle();
  await page.waitForFunction((el) => el.dataset.gateRendered === 'true', handle, { timeout });
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => resolve())));
}

async function activateNav(page, name, mode) {
  const link = page.getByRole('link', { name, exact: true });
  if (mode === 'desktop-hover') {
    await link.hover({ timeout: 120000 });
    await page.waitForTimeout(150);
  }
  const start = performance.now();
  if (mode === 'mobile-touch') {
    await link.tap({ timeout: 120000 });
  } else {
    // Use the same click dispatch for both immediate and hover so hover vs immediate
    // isolates prefetch timing without Playwright's click actionability wait.
    await link.evaluate((el) => el.click());
  }
  return start;
}

(async () => {
  fs.mkdirSync(path.dirname(output), { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const isMobile = scenario === 'mobile-touch';
  const viewport = isMobile ? { width: 390, height: 844 } : { width: 1440, height: 900 };
  const results = [];
  const allErrors = [];

  for (let n = 0; n < samples; n++) {
    const context = await browser.newContext({
      viewport,
      hasTouch: isMobile,
      isMobile,
    });
    const page = await context.newPage();
    await page.addInitScript(() => {
      window.__chartPerformanceGate = true;
    });
    const errors = [];
    let bytes = 0;
    const pendingSizes = [];
    page.on('pageerror', (e) => errors.push(e.message));
    page.on('response', (r) => {
      if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`);
    });
    page.on('requestfinished', (r) => {
      pendingSizes.push(
        r
          .sizes()
          .then((s) => {
            bytes += s.responseBodySize;
          })
          .catch(() => {}),
      );
    });

    const row = { sample: n };
    try {
      // 1. Cold Upcoming load
      let start = performance.now();
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120000 });
      await page.getByRole('heading', { name: 'No upcoming events' }).waitFor({ timeout: 120000 });
      row.upcomingMs = performance.now() - start;
      await Promise.all(pendingSizes.splice(0));
      row.upcomingBytes = bytes;

      // 2. First Fighters visit
      start = await activateNav(page, 'Fighters', scenario);
      await page.getByRole('heading', { name: 'Max Holloway' }).waitFor({ timeout: 120000 });
      row.fighterDataMs = performance.now() - start;
      await waitForChartFrame(page, page.locator('.view:visible .chart').first());
      row.fighterChartMs = performance.now() - start;

      // 3. First Network visit
      start = await activateNav(page, 'Network', scenario);
      await waitForChartFrame(page, page.locator('.view:visible .chart').first());
      row.networkChartMs = performance.now() - start;

      // 4. First Roster visit
      start = await activateNav(page, 'Roster', scenario);
      await page.getByText('171 fighters', { exact: true }).waitFor({ timeout: 120000 });
      row.rosterDataMs = performance.now() - start;
      await waitForChartFrame(page, page.locator('.view:visible .chart').first());
      row.rosterChartMs = performance.now() - start;

      // 5. Parameter change: Roster division Middleweight -> Lightweight
      const rosterChart = page.locator('.view:visible .chart').first();
      await rosterChart.evaluate((el) => {
        delete el.dataset.gateRendered;
      });
      start = performance.now();
      await page.getByRole('combobox', { name: 'Division' }).selectOption('LIGHTWEIGHT');
      await waitForChartFrame(page, rosterChart);
      row.rosterSwitchMs = performance.now() - start;

      // 6. Parameter change: Network division Heavyweight -> Lightweight
      await activateNav(page, 'Network', scenario);
      const networkChart = page.locator('.view:visible .chart').first();
      await networkChart.evaluate((el) => {
        delete el.dataset.gateRendered;
      });
      start = performance.now();
      await page.getByRole('combobox', { name: 'Division' }).selectOption('LIGHTWEIGHT');
      await waitForChartFrame(page, networkChart);
      row.networkSwitchMs = performance.now() - start;

      await Promise.all(pendingSizes.splice(0));
      row.totalBytes = bytes;
      row.canvasCount = await page.locator('canvas').count();
      if (n === 0) {
        row.marks = await page.evaluate(() =>
          performance
            .getEntriesByType('mark')
            .filter((e) => e.name.startsWith('chart:'))
            .map((e) => ({ name: e.name, startTime: Number(e.startTime.toFixed(2)) })),
        );
      }
    } catch (e) {
      row.failure = String(e);
    }
    row.errors = errors;
    allErrors.push(...errors);
    results.push(row);
    await context.close();
  }

  const ok = results.filter((r) => !r.failure);
  const summary = {
    upcomingMs: summarize(ok.map((r) => r.upcomingMs)),
    fighterDataMs: summarize(ok.map((r) => r.fighterDataMs)),
    fighterChartMs: summarize(ok.map((r) => r.fighterChartMs)),
    networkChartMs: summarize(ok.map((r) => r.networkChartMs)),
    rosterDataMs: summarize(ok.map((r) => r.rosterDataMs)),
    rosterChartMs: summarize(ok.map((r) => r.rosterChartMs)),
    rosterSwitchMs: summarize(ok.map((r) => r.rosterSwitchMs)),
    networkSwitchMs: summarize(ok.map((r) => r.networkSwitchMs)),
    upcomingBytes: summarize(ok.map((r) => r.upcomingBytes)),
    totalBytes: summarize(ok.map((r) => r.totalBytes)),
  };

  fs.writeFileSync(
    output,
    JSON.stringify({ url, scenario, samples, viewport, summary, errors: allErrors, results }, null, 2),
  );
  console.log('SUMMARY', JSON.stringify({ scenario, summary, errors: allErrors, failures: results.filter((r) => r.failure).length }));
  if (allErrors.length || results.some((r) => r.failure)) process.exitCode = 1;
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
