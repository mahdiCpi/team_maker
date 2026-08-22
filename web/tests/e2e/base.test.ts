/**
 * Base E2E test utilities and fixtures for team_maker
 * Covers critical user journeys: compose -> build -> run
 */

import { test, expect } from '@playwright/test';

// Base URL for the application
test.use({ baseURL: 'http://localhost:3000' });

// Timeout for API calls and page loads
test.setTimeout(60000);

/**
 * Navigate to the home page and verify it loads
 */
test('Home page loads successfully', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/team_maker/);
});

/**
 * Fixture: Navigate to composer page
 */
export async function navigateToComposer(page: any) {
  await page.goto('/compose');
  await expect(page).toHaveURL(/compose/);
}

/**
 * Fixture: Fill in basic team composition
 */
export async function fillBasicTeamComposition(page: any) {
  // This would be customized based on the actual UI elements
  // For now, just a placeholder that demonstrates the pattern
  await page.getByLabel('Team Name').fill('Test Team');
  await page.getByLabel('Description').fill('E2E test team');
}

/**
 * Fixture: Submit composition form
 */
export async function submitComposition(page: any) {
  await page.getByRole('button', { name: /Compose|Create/ }).click();
  await expect(page).toHaveURL(/build/);
}

/**
 * Fixture: Complete build step
 */
export async function completeBuild(page: any) {
  // Wait for build to complete
  await expect(page.getByText(/Build Complete|Build Successful/)).toBeVisible();
  await page.getByRole('button', { name: /Build|Next/ }).click();
  await expect(page).toHaveURL(/run/);
}

/**
 * Fixture: Run team and verify results
 */
export async function runTeamAndVerify(page: any) {
  await page.getByRole('button', { name: /Run|Start/ }).click();
  
  // Wait for run to complete
  await expect(page.getByText(/Run Complete|Finished/)).toBeVisible({
    timeout: 120000, // Longer timeout for full run
  });
  
  // Verify transcript is visible
  await expect(page.getByText(/Transcript/)).toBeVisible();
}
