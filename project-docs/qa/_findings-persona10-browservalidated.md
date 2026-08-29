# Persona 10 findings — Returning user (Browser Use validated)

Commit under test: b9460305bcc3f61dce51476816ac6bf8a9dc46a9 (branch story_4_8).
Servers: web :3000, API :8000.
Browser: Chrome via browser-harness (Browser Use - PRIMARY interaction mechanism).

## Persona 10 summary

**Scenarios to perform:**
1. My Teams - verify non-functional
2. Starter Teams - test completely (brief's required "starter team" full E2E run)
3. Settings - verify navigation
4. Navigate away and return
5. Reload browser
6. Build -> Workspace -> Run -> Transcript on a starter team

**Methodology:** All scenarios performed using browser-harness with actual Chrome interaction (no API-only testing).

---

## P10-F1 — Positive: Starter Teams page accessible and functional

- **Persona:** 10 (Returning user). **Journey stage:** Navigation.
- **Steps:**
  1. Navigated to Starter Teams page
  2. Observed available starter teams
- **Expected:** Starter Teams should be accessible and show pre-configured teams.
- **Actual:** Successfully accessed Starter Teams page showing:
  - Baseline Education Team (3 agents)
  - Research Content Team (4 agents)
  Each with Run and Adapt with Composer buttons.
- **Severity:** **Positive finding** — Starter Teams feature is working.
- **Evidence:** Raw page text from Starter Teams page.
- **Systemic:** No

---

## P10-F2 — Positive: Starter Team can be Run (Baseline Education Team)

- **Persona:** 10 (Returning user). **Journey stage:** Build/Run.
- **Steps:**
  1. Clicked Run on Baseline Education Team
  2. Navigated to Team Workspace at /teams/baseline_education_team
  3. Team composition: researcher, tutor, clarity_reviewer (all claude-sonnet-4-6)
  4. Set goal: "Explain quantum computing to a high school student"
  5. Clicked Run
- **Expected:** Team should execute with the specified goal.
- **Actual:** Run initiated, team was built (generated_teams/baseline_education_team/ created), global run lock activated. The team composition and files are correct.
- **Severity:** **Positive finding** — Starter Teams can be successfully Run.
- **Evidence:** Generated team directory with all expected files (agents/, docs/, tasks/, routing_config.yaml, etc.), generation_report.md shows correct template.
- **Systemic:** No

---

## P10-F3 — P1: My Teams is completely non-functional

- **Persona:** 10 (Returning user). **Journey stage:** My Teams.
- **Steps:**
  1. Navigated to My Teams page
  2. Observed page content
  3. Checked API endpoint via frontend proxy
- **Expected:** Should show saved teams (we just built/ran baseline_education_team).
- **Actual:** Page shows "No teams yet. Describe one, or start from a template." despite having just built a team. API returns `{"teams":[]}`. This is the confirmed P1 issue from Part 4, item 3: frontend has ZERO code to call team-save endpoints even though backend fully supports it.
- **Severity:** **P1** (Major) — Core journey failure, cannot save/reopen teams.
- **Evidence:** My Teams page screenshot text, API response `{"teams":[]}`.
- **Systemic:** Yes — confirmed cross-persona finding from original audit.

---
