# Findings draft — accumulate here, fold into final report at the end

## F1 — Direct questions asked in the same message as an edit request are silently dropped (no answer ever surfaced)
- Persona: 1 (first-time user)
- Journey stage: Compose/refine
- Steps: On a freshly composed "weekly planner" team (intake_agent → task_breakdown_agent → scheduler_agent → review_agent, all anthropic), sent: "What does the intake_agent do? Also please remove the review_agent, I don't think I need it."
- Expected: Some explanation of intake_agent's role/purpose, then confirmation of removal.
- Actual: review_agent was correctly removed (state matches). The question "what does intake_agent do" was never answered — response was purely mechanical: "Updated: intake_agent -> task_breakdown_agent -> scheduler_agent. Anything you would change about scheduler_agent, or is this ready to build?"
- Reproduced again later in the same session with "Why is everything Anthropic?" (see F2) — same pattern: question ignored, only the actionable part processed.
- Severity: P2 (moderate) — the product silently ignores conversational questions; a beginner has no way to learn what a role does except trial/error. Not a crash, but directly contradicts the "does it teach without overwhelming" success criterion for Persona 1.
- Evidence: project-docs/qa/evidence/p1_s1_followup1.png; DOM text dump in this transcript.

## F2 — Provider-diversification acknowledgment text is indistinguishable from a "no provider change" turn; a later ambiguous request silently reverted the diversification with no disclosure
- Persona: 1 (also directly the regression scenario named in the audit brief, section 4)
- Journey stage: Compose/refine
- Steps (same session as F1, team "weekly_planner", commit b9460305bcc3f61dce51476816ac6bf8a9dc46a9):
  1. Built team defaults to anthropic for all 3 roles (intake_agent, scheduler_agent, task_breakdown_agent) — confirmed via API JSON (`"llm":{"provider":"anthropic",...}` for every desired_roles entry).
  2. Sent: "Why is everything Anthropic? Use different providers where they make sense."
     - Actual routing DID change: intake_agent -> openai, scheduler_agent -> google (via OpenRouter), task_breakdown_agent stayed anthropic. Confirmed via chips in UI.
     - Chat text: "Updated: intake_agent -> task_breakdown_agent -> scheduler_agent. Anything you would change about scheduler_agent, or is this ready to build?" — byte-identical to the PRIOR turn's text (the removal turn), which involved zero provider change. No mention that providers changed, no answer to "why".
  3. Sent: "Choose the best available model for each role."
     - Actual routing SILENTLY REVERTED all 3 roles back to anthropic/claude-sonnet-4-6 (raw API response `"clarification":null`, spec dump confirms all three `llm.provider == "anthropic"`).
     - Chat text: again byte-identical boilerplate template, zero mention that the just-established provider diversity was undone.
  - Verified via raw network capture (`Network.getResponseBody`) on the actual `/api/compose/sessions/{id}/messages` POST responses, not just the rendered DOM — the backend's `clarification` field was `null` on both of these turns, and the frontend's fixed template ("Updated: {role_chain}. Anything you would change about {last_role}, or is this ready to build?") is derived only from role NAMES/order, never from provider/model diffs or from answering the user's actual question.
  - Confirmed template DOES update correctly when role names change (a later rename to `planner_agent` correctly showed "intake_agent -> planner_agent -> scheduler_agent"), so this is not a fully-static string — it's specifically blind to provider/model changes and to free-text questions.
- Why this matters: this is precisely the "conversational truthfulness" regression class called out in the audit brief. No literal false claim is made ("Updated" is technically true — something was updated), but the acknowledgment is uninformative to the point of being misleading: a user who explicitly asked to diversify providers, got it, then asked a followup that silently undid it, has zero way to know from the chat transcript that their diversification request was reverted. They'd have to notice the small provider chips changed back on their own.
- Severity: P1 (major) — provider/tool routing communication is materially incorrect/incomplete, and a user's explicit, satisfied request was silently undone by a later ambiguous one with no disclosure.
- Evidence: raw JSON response bodies captured in this transcript (turn 4 and turn 5), screenshots p1_s1_anthropic_q / p1_s1_turn4_null_clarification (text-only, screenshot API flaked) / p1_s1_rename_result.png.

## F3 — Generated `how_to_run.md` falsely claims no API keys are required when the team is 100% routed to a keyed cloud provider
- Persona: 1 / systemic (would affect every persona)
- Journey stage: Build / generated docs
- Team: weekly_planner, all 3 agents routed anthropic/claude-sonnet-4-6 (confirmed in routing_config.yaml, generation_report.md, and the UI chips)
- File: generated_teams/weekly_planner/docs/how_to_run.md, "## Environment Variables" section reads: "_No API keys required (local models only)._"
- Actual: every single agent requires `ANTHROPIC_API_KEY` to run for real (confirmed by team_config/routing_config/model_routing.md's own routing table, which correctly lists `anthropic` provider for all 3 roles two sections later in the SAME file's sibling doc `model_routing.md`).
- This is the exact defect class named in the audit brief section 5: "how_to_run.md claiming no API keys are required when a tool actually requires one."
- Severity: P1 (major) — a user (or a downstream coding agent) following this doc literally would either hit a runtime auth failure with no warning, or wrongly conclude the team is free/local when it is not. Directly damages trust in generated documentation, and by extension in team_maker's core "explain what will cost money / what's local vs external" promise (audit brief section 12).
- Evidence: file read of generated_teams/weekly_planner/docs/how_to_run.md and docs/model_routing.md (both timestamped 2026-08-23, this session's build).

## F4 — Generated `how_to_run.md` code example references a role/file that does not exist in the generated package
- Same file, "## Running Individual Agents" section: example code opens `agents/architect.yaml`.
- Actual generated files: `agents/intake_agent.yaml`, `agents/planner_agent.yaml`, `agents/scheduler_agent.yaml` — there is no `architect` role anywhere in this team.
- Root cause (suspected, not confirmed): generation_report.md states `**Template:** software_delivery_team` — `architect` is presumably a role name from that base template that leaked into the doc-generation step without being substituted for this team's actual roles.
- Severity: P2 (moderate) — copy-pasting the documented example verbatim raises `FileNotFoundError`. Doesn't block the primary run_example.py path, but it's a concrete "generated documentation not derived from actual configuration" defect (systemic theme, audit brief section 15).
- Evidence: file listing of generated_teams/weekly_planner/agents/ vs. contents of docs/how_to_run.md.

## F5 (minor) — Rename doesn't propagate to display_name/description
- After renaming `task_breakdown_agent` -> `planner_agent` via chat, `agents/planner_agent.yaml` still has `display_name: Task Breakdown Specialist` and a description written in third person about "large goals" that never mentions the new name (only `backstory: An experienced planner_agent.` picked up the new slug).
- Severity: P3 (minor/cosmetic) — not incorrect, just stale/inconsistent naming inside the generated package.

## F6 (minor, a11y) — Composer/refinement textarea aria-label never updates
- The chat input's `aria-label` stays `"Describe your team"` even after the team exists and the visible placeholder has changed to `"Tell team_maker what to change…"`. Screen-reader users refining an existing team would hear the initial-composition label throughout.
- Severity: P3.

## F7 (observation, needs follow-up) — generation_report.md exposes an internal template name ("software_delivery_team") for a completely unrelated domain (weekly personal planning)
- Not necessarily wrong, but if a curious user opens the generation report, "Template: software_delivery_team" for a personal weekly-planning team looks like miscategorization / raises "did it understand my request?" doubt. Needs a second scenario in a different domain to see if this is truly a fixed universal template name (in which case it should probably not be surfaced verbatim to end users) or genuinely selected per-domain (in which case something picked the wrong one for this request).
- Severity: P3 pending further evidence.

## F9 (source-confirmed, needs browser E2E confirmation by persona 4/7 runs) — Tool credentials (e.g. SERPER_API_KEY for web_search) are invisible to every validation layer; the post-build validator only checks file/YAML existence, never tool availability
- Read `team_maker/codegen/templates/tools.py.j2` (the template every generated team's `tools.py` is rendered from) and `team_maker/validation/validator.py` (the ONLY post-generation validator, wired into `generation_report.md`'s "Validation: PASSED/FAILED" + Issues/Warnings sections).
- `tools.py.j2` only registers `"web_search"` in `TOOL_REGISTRY` `if os.environ.get("SERPER_API_KEY")` (similarly `code_reader` needs `OPENAI_API_KEY`, `git_account`/`ci_tool` need `GITHUB_TOKEN`). If the env var is absent, the tool is silently never added to the registry, and `get_tools_for()` just does `print(f"[warn] tool '{name}' not in registry — skipping.")` to server stdout — invisible to the web UI.
- `validator.py`'s entire `OutputValidator.validate()` is exactly 4 checks: required top-level files exist, `agents/<role>.yaml` exists per agent, `tasks/<name>.yaml` exists per task, and all `.yaml` files parse. It NEVER inspects `suggested_tools`, tool env vars, or cross-checks against `TOOL_REGISTRY`/what's actually importable at runtime (`crewai_tools`, `PyGithub`, etc.).
- `SERPER_API_KEY` has zero references anywhere in the codebase outside this one Jinja template — it is not part of `/api/keys/status`, not part of the key-config UI, not part of validation. A user has no way to discover, from anywhere in the product, that a team using `web_search` needs a Serper account/key, until they either read the generated `tools.py` source themselves or run the team and watch server stdout (which the web UI never surfaces).
- Predicted, not-yet-browser-confirmed consequence: a team built with a "research the web" role will show "Validation: Passed" / "No issues found" in `generation_report.md`, its `how_to_run.md`/`model_routing.md` will describe LLM provider requirements but say nothing about `SERPER_API_KEY`, and at actual run time the agent will silently execute with no web_search tool at all — almost certainly hallucinating research results while the UI reports the run as successful. This is being handed to the Persona 4 (student/researcher) and Persona 7 (software engineer, for `git_account`/`ci_tool`/`GITHUB_TOKEN`) test passes to confirm empirically end-to-end (build -> generation_report.md -> actually Run -> transcript content) before we call it CONFIRMED rather than PLAUSIBLE.
- Severity if confirmed end-to-end: P0 candidate — this is exactly "the product confidently claims a capability/result that fundamentally does not exist" (validation passed, docs silent, run reports success) for any tool-requiring team, which the audit brief explicitly flags as P0-caliber. Systemic (affects every non-LLM tool, not a one-off).
- Evidence: team_maker/codegen/templates/tools.py.j2 (lines with `if os.environ.get("SERPER_API_KEY")`, `TOOL_REGISTRY`, `get_tools_for`), team_maker/validation/validator.py (full file, 90 lines, 4 check methods only).

## Environment / setup facts
- Commit under test: b9460305bcc3f61dce51476816ac6bf8a9dc46a9 (branch story_4_8)
- Servers were already running pre-session (npm run dev :3000, uvicorn --reload :8000), TEAM_MAKER_API_KEY auth wiring confirmed working end-to-end (web proxy -> API, no "Authentication required").
- Provider key status (GET /api/keys/status): anthropic available, openai available, google via-openrouter (NOT a direct Google key), groq unsupported-by-runtime (installed CrewAI has no native groq provider), xai via-openrouter, ollama keyless-local (usable=true — NOT yet verified that an Ollama daemon is actually reachable; flagged for Persona 6 test), openrouter available.
- browser-harness screenshot capture (`capture_screenshot` / `Page.captureScreenshot` via CDP) is intermittently flaky — approx 1-in-3 calls time out with no apparent pattern; text-based `document.body.innerText` dumps via `js()` are reliable and used as the primary evidence source, screenshots as secondary/best-effort.

## F8 — Run reports "Complete" / "Run complete." while the final task's actual output is silently truncated mid-sentence
- Persona: 1. Journey stage: Run / Transcript. Team: weekly_planner (all-anthropic, claude-sonnet-4-6), goal: plan next week around a Thursday deadline, Tuesday dentist appointment, 3x exercise.
- All 3 tasks (collect_priorities, break_down_tasks, build_schedule) showed status "Done" with a green "Complete" / "Run complete." banner, no warning icon, no partial/incomplete indicator.
- The final rendered output (both in the workspace panel and in the full "View transcript" view) cuts off mid-markdown-table: the last line is a bare table row header `| **2:00 PM – 3:30 PM**` with no cells filled in and the document ends there — mid Wednesday afternoon. Everything after that point is missing: the rest of Wednesday, all of Thursday (the actual project deadline day — the single most important day in the user's request), Friday, and the weekend.
- Confirmed via `document.body.innerText` on both the live workspace view and the transcript view — identical truncation point in both, so this is the actual stored/generated content, not a rendering artifact.
- Root cause suspected but not confirmed: no `max_tokens` override exists anywhere in `api/` (grepped), so this is very likely the underlying model hitting its own default output-length ceiling for a long, heavily-formatted markdown table (classic `finish_reason: length` pattern) with CrewAI/team_maker not detecting or surfacing that condition. Backend log file referenced by scripts/qa_web_dev.sh did not exist for this server process (it was already running from a prior session via a different launch path), so the raw provider `finish_reason` could not be directly inspected — flagged as PLAUSIBLE root cause, not CONFIRMED.
- Why this matters: this is a direct, high-confidence hit on "misleading success messages" / "run/transcript inconsistencies" from the audit brief. A user relying on this for their actual week — including the Thursday deadline — would not find out the plan is incomplete unless they read the entire output carefully themselves. The system's own status language ("Complete", "Done", "Run complete.") actively asserts full success.
- Severity: P1 (major) — arguably P0-adjacent for this specific run (the single fact the user most needed, the deadline day, is the part that's missing), but scoped as P1 since it's a content/quality defect rather than a security/destructive one.
- Evidence: full innerText dumps captured in this transcript at both the workspace-panel and transcript-modal stage, both ending at the identical cutoff.

## Full E2E run in progress
- weekly_planner (simple no-tool team, all-anthropic after the revert in F2) — goal: "Help me plan next week. I have a work project deadline Thursday, a dentist appointment Tuesday morning, and I want to exercise 3 times." Run started, polling in background (real LLM calls, can take minutes). Will record transcript + final state once complete.
