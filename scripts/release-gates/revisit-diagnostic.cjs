// Opt-in chart marks and a Chromium timeline make actionability delays visible.
const { chromium } = require('../../frontend/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const { performance } = require('perf_hooks');

const samples = Number(process.env.GATE_SAMPLES || 20);
const output = process.env.GATE_OUTPUT || '.scratch/release-gates/revisit-diagnostic.json';
const url = process.env.GATE_URL || 'http://127.0.0.1:18751';
const mode = process.env.GATE_MODE || 'playwright-scroll';
const traceEnabled = process.env.GATE_TRACE !== '0';
const validModes = new Set(['playwright-scroll', 'user-pointer', 'user-keyboard', 'reduced-motion']);
if (!Number.isInteger(samples) || samples < 1) throw new Error('GATE_SAMPLES must be a positive integer');
if (!validModes.has(mode)) throw new Error(`GATE_MODE must be one of: ${[...validModes].join(', ')}`);

function percentile(values, p) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1)];
}

function summarize(values) {
  if (!values.length) return null;
  return {
    n: values.length,
    p50: Number(percentile(values, 50).toFixed(2)),
    p95: Number(percentile(values, 95).toFixed(2)),
    max: Number(Math.max(...values).toFixed(2)),
  };
}

(async () => {
  fs.mkdirSync(path.dirname(output), { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    reducedMotion: mode === 'reduced-motion' ? 'reduce' : 'no-preference',
  });
  const page = await context.newPage();
  await page.addInitScript(() => {
    window.__chartPerformanceGate = true;
  });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('response', (r) => {
    if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`);
  });
  const cdp = traceEnabled ? await context.newCDPSession(page) : null;
  if (cdp) {
    await cdp.send('Tracing.start', {
      categories: 'devtools.timeline,blink.user_timing,loading',
      transferMode: 'ReturnAsStream',
    });
  }
  const results = [];
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120000 });
    for (let n = 0; n < samples; n++) {
      for (const name of ['Fighters', 'Network', 'Roster', 'Upcoming']) {
        const result = { sample: n, view: name };
        const start = performance.now();
        try {
          const link = page.getByRole('link', { name, exact: true });
          if (mode === 'user-keyboard') {
            await link.focus({ timeout: 120000 });
            await page.keyboard.press('Enter');
          } else {
            await link.click({ timeout: 120000 });
          }
          result.clickMs = performance.now() - start;
          if (name !== 'Upcoming') {
            const chart = page.locator('.view:visible .chart').first();
            await chart.waitFor({ state: 'visible', timeout: 120000 });
            const scrollStart = performance.now();
            if (mode === 'playwright-scroll' || mode === 'reduced-motion') {
              await chart.scrollIntoViewIfNeeded({ timeout: 120000 });
            } else {
              const rect = await chart.evaluate((el) => {
                const r = el.getBoundingClientRect();
                const inViewport = r.top >= 0 && r.bottom <= window.innerHeight;
                if (!inViewport) el.scrollIntoView({ behavior: 'instant', block: 'nearest' });
                return { top: Math.round(r.top), bottom: Math.round(r.bottom), inViewport };
              });
              result.beforeScroll = rect;
            }
            result.scrollMs = performance.now() - scrollStart;
            await chart.locator('canvas').first().waitFor({ state: 'visible', timeout: 120000 });
            const handle = await chart.elementHandle();
            await page.waitForFunction((el) => el.dataset.gateRendered === 'true', handle, { timeout: 120000 });
            await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => resolve())));
          } else {
            await page.locator('.view:visible').first().waitFor({ timeout: 120000 });
            await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => resolve())));
          }
          result.totalMs = performance.now() - start;
          result.canvasCount = await page.locator('canvas').count();
        } catch (e) {
          result.failure = String(e);
          result.totalMs = performance.now() - start;
        }
        results.push(result);
        console.log(JSON.stringify(result));
      }
    }
  } finally {
    const marks = await page.evaluate(() =>
      performance
        .getEntriesByType('mark')
        .filter((e) => e.name.startsWith('chart:'))
        .map((e) => ({ name: e.name, startTime: e.startTime })),
    );
    const markCounts = {};
    for (const m of marks) markCounts[m.name] = (markCounts[m.name] || 0) + 1;
    let tracePath = null;
    if (cdp) {
      const completed = new Promise((resolve) => cdp.once('Tracing.tracingComplete', resolve));
      await cdp.send('Tracing.end');
      const { stream } = await completed;
      tracePath = output.replace(/\.json$/, '') + '.trace.json';
      const trace = fs.createWriteStream(tracePath);
      let chunk;
      do {
        chunk = await cdp.send('IO.read', { handle: stream });
        trace.write(chunk.data, chunk.base64Encoded ? 'base64' : 'utf8');
      } while (!chunk.eof);
      await new Promise((resolve, reject) => trace.end((err) => (err ? reject(err) : resolve())));
      await cdp.send('IO.close', { handle: stream });
    }
    const revisits = results.filter((r) => r.sample > 0 && !r.failure);
    const summary = {};
    for (const view of ['Fighters', 'Network', 'Roster', 'Upcoming']) {
      const rows = revisits.filter((r) => r.view === view);
      summary[view] = {
        totalMs: summarize(rows.map((r) => r.totalMs)),
        clickMs: summarize(rows.map((r) => r.clickMs)),
        scrollMs: view === 'Upcoming' ? null : summarize(rows.map((r) => r.scrollMs)),
      };
    }
    fs.writeFileSync(
      output,
      JSON.stringify({ url, mode, samples, viewport: { width: 1440, height: 900 }, summary, markCounts, errors, results, marks, tracePath }, null, 2),
    );
    console.log('SUMMARY', JSON.stringify({ mode, summary, markCounts, errors }));
    if (errors.length || results.some((result) => result.failure)) process.exitCode = 1;
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
