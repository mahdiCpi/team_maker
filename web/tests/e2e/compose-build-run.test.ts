/**
 * Critical user journey E2E test: compose -> build -> run
 * Tests the complete workflow from team composition to execution
 */

import { test, expect } from '@playwright/test';
import {
  navigateToComposer,
  fillBasicTeamComposition,
  submitComposition,
  completeBuild,
  runTeamAndVerify,
} from './base';

// Extend timeout for the full journey
test.setTimeout(180000);

test.describe('Critical User Journey: Compose -> Build -> Run', () => {
  test('Complete workflow from composition to execution', async ({ page }) => {
    // Step 1: Navigate to composer
    await navigateToComposer(page);
    
    // Step 2: Fill in basic team composition
    await fillBasicTeamComposition(page);
    
    // Step 3: Submit composition and navigate to build
    await submitComposition(page);
    
    // Step 4: Complete build step
    await completeBuild(page);
    
    // Step 5: Run team and verify results
    await runTeamAndVerify(page);
    
    // Final verification: we should be on a results page
    await expect(page).toHaveURL(/results|transcript/);
  });

  test('Can navigate through all major pages', async ({ page }) => {
    // Test navigation flow
    await page.goto('/');
    await expect(page.getByRole('link', { name: /Compose/ })).toBeVisible();
    
    await page.getByRole('link', { name: /Compose/ }).click();
    await expect(page).toHaveURL(/compose/);
    
    // Verify we can access other major routes
    await page.goto('/build');
    await expect(page).toHaveURL(/build/);
    
    await page.goto('/run');
    await expect(page).toHaveURL(/run/);
  });

  test('My Teams page loads', async ({ page }) => {
    await page.goto('/my-teams');
    await expect(page).toHaveTitle(/My Teams|team_maker/);
  });

  test('Settings page loads', async ({ page }) => {
    await page.goto('/settings');
    await expect(page).toHaveTitle(/Settings|team_maker/);
  });
});
