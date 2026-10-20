import { expect, test } from '@playwright/test';

test('status page shows the API is healthy', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('API: ok')).toBeVisible();
});

test('readiness sees postgres and redis', async ({ request }) => {
  const r = await request.get('/api/v1/readyz');
  expect(r.status()).toBe(200);
  expect((await r.json()).checks).toEqual({ postgres: 'ok', redis: 'ok' });
});

test('unknown API path is a problem+json 404', async ({ request }) => {
  const r = await request.get('/api/v1/nope');
  expect(r.status()).toBe(404);
  expect(r.headers()['content-type']).toBe('application/problem+json');
});
