import { defineConfig, devices } from '@playwright/test';
import path from 'path';

// `import.meta.url` doesn't parse here: this repo's package.json has no
// `"type": "module"`, so Playwright's config loader requires this file as
// CommonJS, where `__dirname` (not `import.meta`) is the module-relative path.
const PORT = parseInt(process.env.PORT || '3000', 10);

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: path.resolve(__dirname, './tests/e2e'),
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: `http://localhost:${PORT}`,

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',

    /* Capture screenshot after each test failure. */
    screenshot: 'only-on-failure',

    /* Capture video after each test failure. */
    video: 'retain-on-failure',
  },

  /* Only chromium: `package.json`'s `playwright:install` script (and the CI
   * step that runs it) installs `chromium` alone. A wider project matrix
   * here without a matching install step means every other project fails on
   * a missing browser binary on the very first run. Widen both together if
   * cross-browser coverage is wanted later. */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  /* Run your local dev server before starting the tests */
  webServer: {
    command: 'npm run start',
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
  },
});
