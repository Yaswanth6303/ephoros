import { defineConfig, devices } from '@playwright/test';
import { nxE2EPreset } from '@nx/playwright/preset';

// The stack runs in Docker Compose behind Traefik (`just up`); no webServer here.
export default defineConfig({
  ...nxE2EPreset(import.meta.dirname, { testDir: './src' }),
  use: {
    baseURL: process.env['E2E_BASE_URL'] ?? 'https://ephoros.localhost',
    ignoreHTTPSErrors: true, // local mkcert certificate
    trace: 'retain-on-failure',
  },
  // shortcut: Chromium only, add Firefox/WebKit + sharding in M9 (spec §12.1)
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
