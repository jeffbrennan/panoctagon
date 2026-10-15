import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { mockApi } from './fixtures';

test('core views and open fighter search have no WCAG A/AA violations', async ({ page }) => {
  await mockApi(page);
  for (const view of ['upcoming', 'fighters', 'network', 'roster']) {
    await page.goto(`/?view=${view}`);
    await expect(page.locator('main .state.loading')).toHaveCount(0);
    await expect(page.locator('main h1')).toBeVisible();
    await page.locator('.view:not([hidden])').evaluate(async (element) => {
      await Promise.all(
        element
          .getAnimations({ subtree: true })
          .filter((animation) => animation.effect?.getTiming().iterations !== Infinity)
          .map((animation) => animation.finished.catch(() => {})),
      );
    });
    const report = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();
    expect(report.violations, `${view} accessibility`).toEqual([]);
    if (view === 'fighters') {
      await page.getByRole('combobox', { name: 'Find a fighter' }).fill('Blair');
      await expect(page.getByRole('option', { name: /Blair Bravo/ })).toBeVisible();
      const popup = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .analyze();
      expect(popup.violations, 'fighter search accessibility').toEqual([]);
    }
  }
});
