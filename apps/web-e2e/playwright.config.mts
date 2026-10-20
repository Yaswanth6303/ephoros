import { defineConfig, devices } from '@playwright/test';
import { nxE2EPreset } from '@nx/playwright/preset';
import { join } from 'node:path';

// SEED_* credentials: mise loads .env in a dev shell; load it here too for CI and plain shells.
try {
  process.loadEnvFile(join(import.meta.dirname, '../../.env'));
} catch {
  // no .env: rely on the environment
}

// The stack runs in Docker Compose behind Traefik (`just e2e`); no webServer here.
export default defineConfig({
  ...nxE2EPreset(import.meta.dirname, { testDir: './src' }),
  use: {
    baseURL: process.env['E2E_BASE_URL'] ?? 'https://ephoros.localhost',
    ignoreHTTPSErrors: true, // local mkcert certificate
    trace: 'retain-on-failure',
  },
  // shortcut: Chromium only, add Firefox/WebKit + sharding in M9 (spec §12.1)
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    {
      name: 'chromium',
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Chrome'],
        storageState: join(import.meta.dirname, '.auth/analyst.json'),
      },
    },
  ],
});
