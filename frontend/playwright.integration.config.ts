import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './integration',
  outputDir: '../.scratch/integration-results',
  reporter: [['list'], ['html', { outputFolder: '../.scratch/integration-report', open: 'never' }]],
  use: { baseURL: process.env.PANOCTAGON_INTEGRATION_URL || 'http://127.0.0.1:8765', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [
    { name: 'desktop-chromium', use: { browserName: 'chromium' } },
    { name: 'mobile-chromium', use: { ...devices['Pixel 7'], defaultBrowserType: 'chromium' } },
    { name: 'firefox', use: { browserName: 'firefox' } },
    { name: 'webkit', use: { browserName: 'webkit' } },
  ],
  webServer: process.env.PANOCTAGON_INTEGRATION_URL ? undefined : {
    command: 'cd .. && PYTHONPATH=. .venv/bin/python scripts/seed_dashboard_integration.py && PANOCTAGON_API_DATABASE=.scratch/integration/dashboard.duckdb PANOCTAGON_API_HEADSHOTS=.scratch/integration/headshots .venv/bin/python -m uvicorn panoctagon.web.server:app --host 127.0.0.1 --port 8765',
    url: 'http://127.0.0.1:8765/api/health',
    reuseExistingServer: false,
  },
});
