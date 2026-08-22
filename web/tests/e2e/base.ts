/**
 * Fixtures for the critical-journey E2E test (compose -> build -> run).
 *
 * NOT a test file (no top-level `test()` — see `smoke.test.ts` for the plain
 * navigation checks that used to live here). `compose-build-run.test.ts`
 * imports these helpers.
 *
 * Network dependency (Story 4.7 Task 6 disclosure): every `/api/*` call this
 * journey makes is intercepted via `page.route()` with realistic response
 * shapes mirrored from `web/lib/api-types` — nothing here proxies to a real
 * LLM or a running FastAPI process. AD-11 (local-only, no infra) and the
 * project's test-transparency rule both argue against a CI E2E lane that
 * depends on live provider credentials to compose a team. These fixtures
 * prove the real frontend renders and navigates correctly against the real
 * wire shape; they do not exercise the CrewAI runtime itself, which has its
 * own conformance suite (`tests/conformance/`) gated separately.
 *
 * Selectors below are read from the actual components, not guessed:
 * `web/components/composer/composer-input.tsx` (aria-label "Describe your
 * team", `data-slot="composer-send"`), `composer-actions.tsx`
 * (`data-slot="composer-build"`), `build-result.tsx`
 * (`data-slot="build-result-workspace-link"`), `workspace/goal-input.tsx`
 * (aria-label "Describe the goal for this run", `data-slot="workspace-run"`),
 * and `workspace/run-status.tsx` (`data-slot="run-status-label"`). There is
 * no `/compose`, `/build`, or `/run` route — composing happens on `/`, and
 * running happens on `/teams/{slug}` (the Team Workspace).
 */
import type { Page, Route } from '@playwright/test';
import { expect } from '@playwright/test';

export const SESSION_ID = 'e2e-session-1';
export const TEAM_SLUG = 'e2e_test_team';
export const RUN_ID = 'e2e-run-1';

const SESSION_COMPLETE = {
  status: 'complete',
  session_id: SESSION_ID,
  turn: 1,
  turns_remaining: 3,
  spec: {
    team_name: 'E2E Test Team',
    purpose: 'Research a topic and draft a short report.',
    desired_roles: [
      { name: 'researcher', description: 'Gathers information on the topic.' },
      { name: 'writer', description: 'Drafts the report.' },
    ],
    desired_tasks: [
      { name: 'research', description: 'Research the topic.', agent_role: 'researcher', dependencies: [] },
      { name: 'draft', description: 'Draft the report.', agent_role: 'writer', dependencies: ['research'] },
    ],
  },
  clarification: null,
};

const BUILD_RESULT = {
  team_name: 'E2E Test Team',
  output_path: `/tmp/generated_teams/${TEAM_SLUG}`,
  agent_count: 2,
  task_count: 2,
  written_file_count: 4,
  model_substitutions: [],
  validation: { passed: true, issues: [], warnings: [] },
};

const TEAM_PLAN_TASKS = [
  { name: 'research', agent_role: 'researcher', dependencies: [] },
  { name: 'draft', agent_role: 'writer', dependencies: ['research'] },
];

const TEAM_PLAN = {
  team_name: 'E2E Test Team',
  agents: [
    {
      role: 'researcher',
      provider: 'anthropic',
      model: 'claude-sonnet',
      status: 'usable',
      usable: true,
      detail: 'Usable',
      fix_hint: null,
    },
    {
      role: 'writer',
      provider: 'anthropic',
      model: 'claude-sonnet',
      status: 'usable',
      usable: true,
      detail: 'Usable',
      fix_hint: null,
    },
  ],
  tasks: TEAM_PLAN_TASKS,
};

const RUN_RUNNING = {
  status: 'running',
  run_id: RUN_ID,
  team_slug: TEAM_SLUG,
  team_name: 'E2E Test Team',
  tasks: TEAM_PLAN_TASKS,
  result: null,
  transcript_available: false,
  failure_reason: null,
};

const RUN_COMPLETE = {
  ...RUN_RUNNING,
  status: 'complete',
  result: {
    final_output: 'The report is complete.',
    task_results: [
      { name: 'research', agent_role: 'researcher', output: 'Findings on the topic.' },
      { name: 'draft', agent_role: 'writer', output: 'The report is complete.' },
    ],
  },
  transcript_available: true,
};

async function json(route: Route, status: number, body: unknown) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
}

/**
 * Install request mocks for the whole compose -> build -> run journey.
 * Call before navigating to `/`.
 */
export async function mockComposeBuildRunApi(page: Page): Promise<void> {
  // Lowest priority: anything under /api/ this journey doesn't otherwise
  // stub gets a fast, deterministic 404 instead of a real network attempt
  // (there is no backend process behind this webServer — see module docstring).
  await page.route('**/api/**', (route) => json(route, 404, { error: { code: 'not_found', message: 'unmocked in E2E' } }));

  await page.route('**/api/keys/status', (route) =>
    json(route, 200, {
      overall: 'has-keys',
      providers: [],
      key_config_path: '',
      load_warnings: [],
      any_key_present: true,
      needs_restart_to_author: [],
    })
  );

  await page.route(`**/api/keys/check/${SESSION_ID}`, (route) =>
    json(route, 200, {
      overall: 'all-good',
      blocked: false,
      blocking_reason: null,
      roles: [],
      providers: [],
      key_config_path: '',
      load_warnings: [],
      any_key_present: true,
      needs_restart_to_author: [],
    })
  );

  await page.route('**/api/compose/sessions', (route) =>
    route.request().method() === 'POST' ? json(route, 201, SESSION_COMPLETE) : route.fallback()
  );

  await page.route(`**/api/compose/sessions/${SESSION_ID}/build`, (route) => json(route, 200, BUILD_RESULT));

  await page.route(`**/api/runs/teams/${TEAM_SLUG}`, (route) => json(route, 200, TEAM_PLAN));

  await page.route('**/api/runs', (route) =>
    route.request().method() === 'POST' ? json(route, 201, RUN_RUNNING) : route.fallback()
  );

  // First poll reports "running", every poll after reports "complete" — this
  // exercises the Workspace's poll loop instead of resolving on the very
  // first request.
  let runPolls = 0;
  await page.route(`**/api/runs/${RUN_ID}`, (route) => {
    runPolls += 1;
    return json(route, 200, runPolls < 2 ? RUN_RUNNING : RUN_COMPLETE);
  });

  await page.route(`**/api/runs/${RUN_ID}/transcript`, (route) =>
    json(route, 200, {
      available: true,
      entries: [
        {
          sequence: 1,
          kind: 'task_completed',
          agent_role: 'writer',
          task_name: 'draft',
          content: 'Draft finished: a one-paragraph report on the topic.',
          target_role: null,
        },
      ],
    })
  );

  await page.route(`**/api/teams/${TEAM_SLUG}/record-run`, (route) => json(route, 200, { ok: true }));
}

/**
 * Pre-seed the first-visit orientation dialog's "dismissed" flag
 * (`web/components/composer/first-visit-orientation.tsx`'s
 * `team_maker_orientation_shown` localStorage key) so a fresh browser
 * context doesn't show a blocking modal mid-journey. Must run before
 * `page.goto()` — `addInitScript` only affects future navigations.
 */
export async function skipFirstVisitOrientation(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('team_maker_orientation_shown', 'true');
  });
}

/** Fixture: navigate to the Composer. It lives at `/` — there is no `/compose` route. */
export async function navigateToComposer(page: Page) {
  await skipFirstVisitOrientation(page);
  await page.goto('/');
  await expect(page.getByLabel('Describe your team')).toBeVisible();
}

/** Fixture: send the first turn's intent and wait for the mocked spec to arrive. */
export async function composeTeam(page: Page) {
  await page.getByLabel('Describe your team').fill(
    'A team that researches a topic and drafts a short report about it.'
  );
  await page.locator('[data-slot="composer-send"]').click();
  await expect(page.locator('[data-slot="composer-build"]')).toBeVisible();
}

/** Fixture: build the composed team and open its Workspace. */
export async function buildAndOpenWorkspace(page: Page) {
  await page.locator('[data-slot="composer-build"]').click();
  await expect(page.locator('[data-slot="build-result"]')).toBeVisible();
  await page.locator('[data-slot="build-result-workspace-link"]').click();
  await expect(page).toHaveURL(new RegExp(`/teams/${TEAM_SLUG}$`));
}

/** Fixture: give the built team a goal, run it, and wait for completion. */
export async function runTeamAndVerify(page: Page) {
  await page.getByLabel('Describe the goal for this run').fill('Write a one-paragraph report.');
  await page.locator('[data-slot="workspace-run"]').click();

  await expect(page.locator('[data-slot="run-status-label"]')).toHaveText('Complete', {
    timeout: 15_000,
  });

  await page.locator('[data-slot="workspace-open-transcript"]').click();
  const dialog = page.locator('[data-slot="workspace-transcript-dialog"]');
  await expect(dialog.getByText('Draft finished: a one-paragraph report on the topic.')).toBeVisible();
}
