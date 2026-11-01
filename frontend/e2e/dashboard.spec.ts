import { test, expect } from '@playwright/test';
import { mockApi, upcoming } from './fixtures';

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test('upcoming starts without loading charts or hidden analytics', async ({ page }) => {
  const scripts: string[] = [];
  const data: string[] = [];
  page.on('request', (request) => {
    if (request.resourceType() === 'script') scripts.push(request.url());
    if (request.url().includes('/api/')) data.push(request.url());
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: upcoming[0].event_title })).toBeVisible();
  await expect(page.locator('.matchup')).toHaveCount(2);
  expect(scripts.some((url) => /echarts|\/chart[.-]/.test(url))).toBe(false);
  expect(data.some((url) => /analytics/.test(url))).toBe(false);
  await expect(page.locator('canvas')).toHaveCount(0);
});

test('matchup filters, event switching, and profile links work', async ({ page }, testInfo) => {
  await page.goto('/');
  const division = page.getByRole('combobox', { name: 'Division' });
  await division.selectOption('LIGHTWEIGHT');
  await expect(page.locator('.matchup')).toHaveCount(1);
  await expect(page.getByText('Casey Charlie', { exact: true })).toBeVisible();
  await division.selectOption('ALL');
  if (testInfo.project.name.includes('mobile')) {
    const card = page.locator('.matchup').first();
    await expect(card.locator('.comparison')).toBeHidden();
    await card.getByRole('button', { name: 'Compare fighters' }).click();
    await expect(card.locator('.comparison')).toBeVisible();
    await expect(card.getByText('+4″', { exact: true })).toBeVisible();
  }
  await page.getByRole('combobox', { name: 'Event', exact: true }).selectOption('later');
  await expect(page.getByRole('heading', { name: 'UFC 999', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Alex Alpha', exact: true }).click();
  await expect(page).toHaveURL(/fighter=alpha/);
  await expect(page.getByRole('heading', { name: 'Alex Alpha', exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'UFC 999', exact: true })).toBeVisible();
});

test('fighter deep links avoid fetching the upcoming view', async ({ page }) => {
  const api: string[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/')) api.push(r.url());
  });
  await page.goto('/?view=fighters&fighter=alpha');
  await expect(page.getByRole('heading', { name: 'Alex Alpha' })).toBeVisible();
  await page.locator('.chart').first().scrollIntoViewIfNeeded();
  await expect(page.locator('canvas').first()).toBeVisible();
  expect(api.some((url) => /\/upcoming/.test(url))).toBe(false);
  await page.getByRole('tab', { name: 'History' }).click();
  await expect(page.getByRole('table')).toBeVisible();
  await expect(page.getByRole('table').locator('tbody tr')).toHaveCount(5);
  await page.getByRole('tab', { name: 'Striking' }).click();
  await expect(page.getByRole('heading', { name: 'Strikes landed vs. absorbed' })).toBeVisible();
});

test('fighter search supports keyboard selection and escape', async ({ page }) => {
  await page.goto('/?view=fighters&fighter=alpha');
  const search = page.getByRole('combobox', { name: 'Find a fighter' });
  await search.fill('Blair');
  await expect(page.getByRole('option', { name: /Blair Bravo/ })).toBeVisible();
  await search.press('ArrowDown');
  await search.press('Enter');
  await expect(page.getByRole('heading', { name: 'Blair Bravo', exact: true })).toBeVisible();
  await expect(page).toHaveURL(/fighter=bravo/);
  await search.fill('Alex');
  await search.press('Escape');
  await expect(search).toHaveAttribute('aria-expanded', 'false');
});

test('network selection and opponent filtering do not refetch data', async ({ page }) => {
  const requests: string[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/analytics/network')) requests.push(r.url());
  });
  await page.goto('/?view=network');
  await expect(page.locator('canvas')).toBeVisible();
  const before = requests.length;
  await page.getByRole('combobox', { name: 'Select a fighter' }).selectOption('alpha');
  await page.getByRole('checkbox', { name: 'Opponents only' }).check();
  await expect(page.getByRole('img', { name: /Network of 2 UFC fighters/ })).toBeVisible();
  await expect(
    page
      .getByRole('region', { name: 'Head-to-head records' })
      .getByRole('link', { name: 'Blair Bravo' }),
  ).toBeVisible();
  expect(requests.length).toBe(before);
  await page.getByRole('button', { name: 'View profile' }).click();
  await expect(page.getByRole('heading', { name: 'Alex Alpha', exact: true })).toBeVisible();
});

test('roster pagination, filtering, sorting, and retained navigation state work', async ({
  page,
}) => {
  await page.goto('/?view=roster');
  await expect(page.locator('.data-table tbody tr')).toHaveCount(20);
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.getByText('21–40 of 45', { exact: true })).toBeVisible();
  await page.getByRole('searchbox', { name: 'Search' }).fill('Alex');
  await expect(page.locator('.data-table tbody tr')).toHaveCount(1);
  await expect(page.getByText('1–1 of 1', { exact: true })).toBeVisible();
  await page.getByRole('combobox', { name: 'Division' }).selectOption('LIGHTWEIGHT');
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Network' })
    .click();
  await expect(page.getByRole('heading', { name: 'Network', exact: true })).toBeVisible();
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Roster' })
    .click();
  await expect(page.getByRole('combobox', { name: 'Division' })).toHaveValue('LIGHTWEIGHT');
  await expect(page.getByRole('searchbox', { name: 'Search' })).toHaveValue('Alex');
  await page.getByRole('searchbox', { name: 'Search' }).clear();
  await page.getByRole('button', { name: /^Fighter ↑|^Fighter$/ }).click();
  await expect(page.locator('.data-table tbody tr').first()).toContainText('Alex Alpha');
});

test('layout fits small phones, tablets, and desktops with no page errors', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const view of ['upcoming', 'fighters', 'network', 'roster']) {
      await page.goto(view === 'upcoming' ? '/' : `/?view=${view}`);
      await expect(page.locator('main .state.loading')).toHaveCount(0);
      await expect(page.locator('main h1')).toBeVisible();
      await expect
        .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
        .toBeLessThanOrEqual(width);
      const charts = page.locator('.chart');
      for (let i = 0; i < (await charts.count()); i++) {
        await charts.nth(i).scrollIntoViewIfNeeded();
        await expect(charts.nth(i).locator('canvas')).toBeVisible();
      }
    }
  }
  expect(errors).toEqual([]);
});

test('failed requests can be retried and an empty calendar stays usable', async ({ page }) => {
  let attempts = 0;
  await page.route('**/api/upcoming', (route) =>
    route.fulfill({
      status: ++attempts === 1 ? 503 : 200,
      contentType: 'application/json',
      body: attempts === 1 ? '{}' : '[]',
    }),
  );
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Unable to load upcoming events' })).toBeVisible();
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('heading', { name: 'No upcoming events' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible();
});

test('fighter detail tabs support arrow, home, and end keys', async ({ page }) => {
  await page.goto('/?view=fighters&fighter=alpha');
  const profile = page.getByRole('tab', { name: 'Profile' });
  await profile.focus();
  await profile.press('ArrowRight');
  const history = page.getByRole('tab', { name: 'History' });
  await expect(history).toBeFocused();
  await expect(history).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('table')).toBeVisible();
  await history.press('End');
  const striking = page.getByRole('tab', { name: 'Striking' });
  await expect(striking).toBeFocused();
  await expect(striking).toHaveAttribute('aria-selected', 'true');
  await striking.press('Home');
  await expect(profile).toBeFocused();
  await expect(profile).toHaveAttribute('tabindex', '0');
  await expect(history).toHaveAttribute('tabindex', '-1');
});

test('changing fighter keeps the existing chart while the next profile loads', async ({ page }) => {
  await page.goto('/?view=fighters&fighter=alpha');
  await page.locator('.chart').first().scrollIntoViewIfNeeded();
  const canvas = page.locator('.chart').first().locator('canvas');
  await expect(canvas).toBeVisible();
  const original = await canvas.elementHandle();
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  await page.route('**/api/fighter/bravo/analytics', async (route) => {
    await gate;
    const { profile, bravo } = await import('./fixtures');
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(profile(bravo)) });
  });
  await page.getByRole('combobox', { name: 'Find a fighter' }).fill('Blair');
  await page.getByRole('option', { name: /Blair Bravo/ }).click();
  await expect(page.getByRole('status')).toHaveText('Loading fighter…');
  expect(await canvas.evaluate((node, previous) => node === previous, original)).toBe(true);
  release();
  await expect(page.getByRole('heading', { name: 'Blair Bravo', exact: true })).toBeVisible();
  expect(await canvas.evaluate((node, previous) => node === previous, original)).toBe(true);
});

test('a failed view chunk can recover by reloading its bookmarked route', async ({ page }) => {
  let fail = true;
  await page.route('**/src/views/Fighters.svelte*', (route) => {
    if (!fail) return route.continue();
    return route.fulfill({
      status: 503,
      contentType: 'text/plain',
      body: 'Temporarily unavailable',
    });
  });
  await page.goto('/');
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Fighters' })
    .click();
  await expect(page.getByRole('heading', { name: 'This view could not load' })).toBeVisible();
  fail = false;
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page).toHaveURL(/view=fighters/);
  await expect(page.getByRole('heading', { name: 'Alex Alpha', exact: true })).toBeVisible();
});

test('a slow obsolete roster response cannot replace a newer division', async ({ page }) => {
  const { roster } = await import('./fixtures');
  let release!: () => void;
  let started!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  const pending = new Promise<void>((resolve) => (started = resolve));
  await page.route('**/api/analytics/roster?division=LIGHTWEIGHT', async (route) => {
    started();
    await gate;
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        ...roster,
        fighters: [{ ...roster.fighters[0], fighter_name: 'Old lightweight response' }],
      }),
    });
  });
  await page.route('**/api/analytics/roster?division=HEAVYWEIGHT', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        ...roster,
        fighters: [{ ...roster.fighters[0], fighter_name: 'New heavyweight response' }],
      }),
    }),
  );
  await page.goto('/?view=roster');
  const division = page.getByRole('combobox', { name: 'Division' });
  await division.selectOption('LIGHTWEIGHT');
  await pending;
  await division.selectOption('HEAVYWEIGHT');
  await expect(page.getByRole('link', { name: 'New heavyweight response' })).toBeVisible();
  release();
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
  );
  await expect(page.getByRole('link', { name: 'New heavyweight response' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Old lightweight response' })).toHaveCount(0);
});

test('returning to a fighter sub-tab preserves its chart instance', async ({ page }) => {
  await page.goto('/?view=fighters&fighter=alpha');
  const profilePanel = page.getByRole('tabpanel', { name: 'Profile', exact: true });
  await profilePanel.locator('.chart').first().scrollIntoViewIfNeeded();
  const canvas = profilePanel.locator('canvas').first();
  await expect(canvas).toBeVisible();
  const original = await canvas.elementHandle();
  await page.getByRole('tab', { name: 'Striking', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Strikes landed vs. absorbed' })).toBeVisible();
  await page.getByRole('tab', { name: 'Profile', exact: true }).click();
  expect(await canvas.evaluate((node, previous) => node === previous, original)).toBe(true);
});

test('resetting the network clears local focus and selection', async ({ page }) => {
  await page.goto('/?view=network');
  const fighter = page.getByRole('combobox', { name: 'Select a fighter' });
  await fighter.selectOption('alpha');
  await page.getByRole('checkbox', { name: 'Opponents only' }).check();
  await page.getByRole('button', { name: 'Reset view', exact: true }).click();
  await expect(fighter).toHaveValue('');
  await expect(page.getByRole('checkbox', { name: 'Opponents only' })).not.toBeChecked();
  await expect(page.getByRole('region', { name: 'Head-to-head records' })).toHaveCount(0);
});

test('stale upcoming data refreshes on return and retains content after a failed update', async ({ page }) => {
  await page.addInitScript(() => {
    const initial = Date.now();
    (window as any).testNow = initial;
    Date.now = () => (window as any).testNow;
  });
  let attempts = 0;
  await page.route('**/api/upcoming', (route) => {
    attempts++;
    if (attempts === 2) return route.fulfill({ status: 503, body: '{}' });
    return route.fulfill({ json: attempts === 1 ? upcoming : [upcoming[1]] });
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: upcoming[0].event_title })).toBeVisible();
  await page.getByRole('link', { name: 'Roster', exact: true }).click();
  await page.evaluate(() => { (window as any).testNow += 120_001; });
  await page.getByRole('link', { name: 'Upcoming', exact: true }).click();
  await expect(page.getByText(/Could not update upcoming events/)).toBeVisible();
  await expect(page.getByRole('heading', { name: upcoming[0].event_title })).toBeVisible();
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(page.getByRole('heading', { name: upcoming[1].event_title })).toBeVisible();
  expect(attempts).toBe(3);
});
