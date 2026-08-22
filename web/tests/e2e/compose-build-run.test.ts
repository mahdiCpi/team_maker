/**
 * Critical user journey E2E test: compose -> build -> run.
 *
 * Drives the real single-page Composer flow (there is no `/compose`,
 * `/build`, or `/run` route — see `base.ts`'s module docstring for why the
 * network layer is mocked rather than proxied to a live LLM).
 */

import { test } from '@playwright/test';
import {
  mockComposeBuildRunApi,
  navigateToComposer,
  composeTeam,
  buildAndOpenWorkspace,
  runTeamAndVerify,
} from './base';

test.describe('Critical User Journey: Compose -> Build -> Run', () => {
  test.beforeEach(async ({ page }) => {
    await mockComposeBuildRunApi(page);
  });

  test('Complete workflow from composition to execution', async ({ page }) => {
    await navigateToComposer(page);
    await composeTeam(page);
    await buildAndOpenWorkspace(page);
    await runTeamAndVerify(page);
  });
});
