// @ts-check
// AUTO-GENERATED FILE - DO NOT EDIT
// TDAD manages this file. Put custom overrides in .tdad/playwright.user.js.

const config = {
  testDir: './workflows',
  // Cross-process lock for all Playwright runs using TDAD config.
  globalSetup: './playwright-global-lock.cjs',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
};

export default config;
