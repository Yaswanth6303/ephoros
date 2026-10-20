import { expect, test } from '@playwright/test';
import { storageStateFor, users } from './users';

// Better Auth allows 3 sign-ins per 10 s per IP: these two plus the wrong-password test are the
// suite's only sign-ins. Every other test reuses the saved sessions.
for (const role of ['analyst', 'admin'] as const) {
  test(`sign in as ${role}`, async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(users[role].email);
    await page.getByLabel('Password').fill(users[role].password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByText('API: ok')).toBeVisible();
    await page.context().storageState({ path: storageStateFor(role) });
  });
}
