import { expect, test } from '@playwright/test';
import { storageStateFor, users } from './users';

test.describe('anonymous', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('anonymous visit redirects to login', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/login\?returnUrl=%2F$/);
  });

  test('wrong password shows an error', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(users.analyst.email);
    await page.getByLabel('Password').fill('definitely-wrong');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('alert')).toHaveText(
      'Invalid email or password',
    );
  });

  test('API rejects requests without a token', async ({ request }) => {
    const r = await request.get('/api/v1/me');
    expect(r.status()).toBe(401);
    expect(r.headers()['content-type']).toBe('application/problem+json');
  });
});

test('analyst sees their identity from the API', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('API: ok')).toBeVisible();
  await expect(page.getByRole('banner')).toContainText(users.analyst.email);
  await expect(page.getByRole('banner')).toContainText('analyst');
});

test.describe('admin', () => {
  // the admin session is used only here, so signing it out cannot break other tests
  test.use({ storageState: storageStateFor('admin') });

  test('admin signs out and returns to login', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('banner')).toContainText('admin');
    await page.getByRole('button', { name: 'Sign out' }).click();
    await expect(page).toHaveURL(/\/login/);
    await page.goto('/');
    await expect(page).toHaveURL(/\/login/);
  });
});
