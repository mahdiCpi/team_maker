/**
 * Basic navigation smoke tests. Hit real routes and real nav labels (see
 * `web/lib/nav-items.ts`) — there is no `/compose`, `/build`, or `/run`
 * route; the Composer lives at `/`.
 */
import { test, expect } from '@playwright/test';
import { skipFirstVisitOrientation } from './base';

test.describe('Navigation smoke tests', () => {
  test('Home page (the Composer) loads successfully', async ({ page }) => {
    await skipFirstVisitOrientation(page);
    await page.goto('/');
    await expect(page).toHaveTitle(/team_maker/);
    await expect(page.getByLabel('Describe your team')).toBeVisible();
  });

  test('Can navigate through the main nav destinations', async ({ page }) => {
    await skipFirstVisitOrientation(page);
    await page.goto('/');

    await page.getByRole('link', { name: 'Starter Teams' }).click();
    await expect(page).toHaveURL(/\/starter-teams$/);

    await page.getByRole('link', { name: 'My Teams' }).click();
    await expect(page).toHaveURL(/\/my-teams$/);

    await page.getByRole('link', { name: 'New Team' }).click();
    await expect(page).toHaveURL(/\/$/);
  });

  test('My Teams page loads', async ({ page }) => {
    await page.goto('/my-teams');
    await expect(page).toHaveTitle('My Teams · team_maker');
  });

  test('Settings page loads', async ({ page }) => {
    await page.goto('/settings');
    await expect(page).toHaveTitle('Settings · team_maker');
  });
});
