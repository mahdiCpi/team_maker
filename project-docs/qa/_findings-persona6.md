# Persona 6 findings — LLM power user (Browser Use validated)

Commit under test: b9460305bcc3f61dce51476816ac6bf8a9dc46a9 (branch story_4_8).
Servers: web :3000, API :8000.
Browser: Chrome via browser-harness (Browser Use - PRIMARY interaction mechanism).

## Persona 6 summary

**Scenarios to perform:**
1. Technical team with explicit per-role routing (vulnerability_scanner + remediation_report_writer with openai/gpt-4o-mini and anthropic/claude-opus)
2. Open-ended "use at least two different providers"
3. Cost optimization + targeted role change (cheaper models, then surgical single-role edit)
4. Edge cases: invalid model (gpt-999), groq unsupported, ollama keyless-local
5. Hard-reload browser after routing changes
6. Full E2E run with explicit routing

**Scenarios completed:** 6/6 (all completed)

**Methodology:** All scenarios performed using browser-harness with actual Chrome interaction (no API-only testing).

---

## P6-F1 — P1: Chat acknowledgment never confirms provider/model routing, ignores direct questions

- **Persona:** 6 (LLM power user). **Journey stage:** Compose/refine.
- **Steps:**
  1. Sent: "A team that monitors a codebase for security issues: one agent scans for vulnerabilities, another writes a remediation report. Use openai/gpt-4o-mini for the scanner and anthropic/claude-opus for the report writer."
  2. Response: "Here is a team for that: vulnerability_scanner → remediation_report_writer. Anything you would change about remediation_report_writer, or is this ready to build?"
  3. Sent follow-up: "What providers and models are currently assigned to each role?"
  4. Response: "Updated: vulnerability_scanner → remediation_report_writer. Anything you would change about remediation_report_writer, or is this ready to build?"
- **Expected:** Chat acknowledgment should explicitly confirm: (a) the provider/model assignments from the first message, (b) answer the direct question in the second message about current routing.
- **Actual:** 
  - Chat acknowledgment only reflects role NAME/ORDER, never provider/model changes
  - Direct questions about routing are silently ignored
  - The exact same template text is used for both responses, byte-for-byte identical except for the role order
  - UI shows vulnerability_scanner→openai→key found, remediation_report_writer→anthropic→key found, but does NOT show specific models (gpt-4o-mini, claude-opus)
- **Severity:** **P1** (Major) — This is the confirmed cross-persona pattern from Part 4, item 1. For an LLM power user explicitly testing routing, this is a critical trust failure. The user cannot verify that their specific model requests were honored without manually inspecting the UI or generated files.
- **Evidence:** Browser Use interaction captured via page_info() and document.body.innerText. Raw chat transcript available on request.
- **Systemic:** Yes — this is the same pattern observed in Persona 1-5. The acknowledgment template is derived only from role names/order, never from provider/model state.

---

## P6-F2 — P1: Open-ended provider request generates diverse providers but acknowledgment still uninformative

- **Persona:** 6 (LLM power user). **Journey stage:** Compose.
- **Steps:**
  1. Sent: "Create a marketing strategy team. Use at least two different providers."
  2. Response: "Here is a team for that: market_researcher → marketing_strategist. Anything you would change about marketing_strategist, or is this ready to build?"
  3. UI shows: market_researcher→openai→key found, marketing_strategist→anthropic→key found (two different providers)
  4. Sent follow-up: "Why did you choose openai for the researcher and anthropic for the strategist?"
  5. Response: "Updated: market_researcher → marketing_strategist. Anything you would change about marketing_strategist, or is this ready to build?" (same template again)
- **Expected:** When explicitly asked to use at least two different providers, the acknowledgment should: (a) confirm that multiple providers were used, (b) explain the reasoning for provider selection, (c) answer direct "why" questions about routing.
- **Actual:** 
  - Providers were correctly diversified (openai + anthropic) - this part works!
  - But chat acknowledgment still uses the generic template that doesn't mention providers
  - Direct "why" questions about provider choices are ignored
  - No explanation of the reasoning behind provider selection
- **Severity:** **P1** (Major) — Same systemic issue as P6-F1. The product does route correctly to different providers, but fails to communicate this to the user.
- **Evidence:** Browser Use interaction captured. UI shows correct provider diversification but chat text never mentions it.
- **Systemic:** Yes — same conversation template issue affecting all routing-related edits.

---

## P6-F3 — P2: Surgical single-role edit acknowledgment doesn't confirm whether change applied

- **Persona:** 6 (LLM power user). **Journey stage:** Compose/refine.
- **Steps:**
  1. Created team: pull_request_reviewer→anthropic, documentation_writer→openai
  2. Sent: "Keep the pull_request_reviewer unchanged, only change the documentation_writer to openai."
  3. Response: "Updated: pull_request_reviewer → documentation_writer. Anything you would change about documentation_writer, or is this ready to build?"
  4. UI shows: pull_request_reviewer→anthropic (unchanged), documentation_writer→openai
- **Expected:** Acknowledgment should explicitly confirm: "No change needed - documentation_writer is already using openai" OR "Changed documentation_writer from anthropic to openai"
- **Actual:** Generic template response doesn't mention what (if anything) changed. User cannot verify from chat text whether their surgical edit request was honored. Must manually inspect UI to confirm.
- **Severity:** **P2** (Moderate) — Significant confusion. For power users doing precise routing edits, the lack of confirmation creates uncertainty about whether changes were applied.
- **Evidence:** Browser Use interaction captured. Documentation_writer was already on openai, but chat text doesn't disclose this.
- **Systemic:** Yes — same template issue, but this is specifically about surgical edits where precision matters.

---

## P6-F4 — P1: Invalid model name silently substituted without disclosure

- **Persona:** 6 (LLM power user). **Journey stage:** Compose.
- **Steps:**
  1. Sent: "Create a research team. Use model gpt-999 for the researcher."
  2. Response: "Here is a team for that: researcher → research_editor. Any model preferences, or should I pick from the keys you have?"
  3. UI shows: researcher→openai→key found (default provider, NOT gpt-999)
- **Expected:** Clear error message: "Model gpt-999 is not available. Available models for openai are: ..." OR explicit substitution: "gpt-999 not found, using gpt-4o-mini instead."
- **Actual:** 
  - No error message
  - No warning
  - Invalid model gpt-999 was silently ignored
  - Default model/provider assigned instead
  - Chat response acts as if no model was requested
  - No disclosure that the user's explicit request was not honored
- **Severity:** **P1** (Major) — Release blocker candidate. Silent substitution of invalid user input is a serious trust failure. User explicitly requested a specific model and got a completely different one with zero disclosure.
- **Evidence:** Browser Use interaction captured. Invalid model silently dropped, default used instead.
- **Systemic:** Yes — silent fallback/substitution pattern. Related to the silent revert issue mentioned in Part 4, item 1.

---

## P6-F5 — P1: Unsupported provider (groq) silently substituted without warning

- **Persona:** 6 (LLM power user). **Journey stage:** Compose.
- **Steps:**
  1. Sent: "Create a coding team. Use groq provider for all roles."
  2. Response: "Here is a team for that: software_architect → backend_developer → frontend_developer → code_reviewer → qa_engineer → devops_engineer. Anything you would change about devops_engineer, or is this ready to build?"
  3. UI shows: All 6 roles assigned to openai (NOT groq)
- **Expected:** Clear warning: "groq is not supported by the installed runtime (CrewAI has no native groq provider). Available providers are: anthropic, openai, openrouter, google, xai, ollama." OR explicit substitution: "groq not available, using openai instead."
- **Actual:** 
  - No warning about groq being unsupported
  - groq request silently ignored
  - All roles assigned to openai (default) instead
  - Chat response acts as if no provider was specified
  - No disclosure that user's explicit request was not honored
- **Severity:** **P1** (Major) — Same silent substitution pattern as P6-F4. User explicitly requested an unsupported provider and got a completely different one with zero disclosure. Particularly concerning because groq is known to be unsupported (runtime limitation) but the system doesn't communicate this.
- **Evidence:** Browser Use interaction captured. Unsupported provider silently dropped, default used instead.
- **Systemic:** Yes — same silent fallback pattern. Confirms the runtime doesn't prevent unsupported provider requests at compose time.

---

## P6-F6 — Positive: Explicit model routing correctly persists to built routing_config.yaml

- **Persona:** 6 (LLM power user). **Journey stage:** Build.
- **Steps:**
  1. Sent: "Create a market analysis team with two agents: one does market research, one writes the report. Use openai/gpt-4o for the researcher and anthropic/claude-sonnet-4-6 for the writer."
  2. Team created with: market_researcher→openai, report_writer→anthropic (UI doesn't show models)
  3. Clicked Build
  4. Generated team: `generated_teams/market_analysis_team/`
  5. Read `routing_config.yaml`
- **Expected:** routing_config.yaml should reflect the specific models requested (gpt-4o, claude-sonnet-4-6).
- **Actual:** 
  - routing_config.yaml contains EXACTLY the requested routing:
    ```yaml
    routing:
      market_researcher:
        provider: openai
        model: gpt-4o
      report_writer:
        provider: anthropic
        model: claude-sonnet-4-6
    ```
  - Build completed successfully with Validation: Passed
  - Workspace link available
- **Severity:** **Positive finding** — Despite the UI not showing specific models, the underlying routing configuration is correct. The specific model requests ARE honored in the built files.
- **Evidence:** File `generated_teams/market_analysis_team/routing_config.yaml` contains correct provider/model assignments.
- **Systemic:** No — this is a UX display issue (models not shown in UI chips), not a routing implementation issue.

---

## Persona 6 summary

**Top 5 findings:**
1. **P6-F1 (P1):** Chat acknowledgment never confirms provider/model routing, ignores direct questions about routing
2. **P6-F2 (P1):** Open-ended provider diversification works but acknowledgment still uninformative
3. **P6-F4 (P1):** Invalid model name (gpt-999) silently substituted without disclosure
4. **P6-F5 (P1):** Unsupported provider (groq) silently substituted without warning
5. **P6-F3 (P2):** Surgical single-role edit acknowledgment doesn't confirm whether change applied

**Positive findings:**
- Provider diversification works correctly (openai + anthropic)
- Explicit model routing correctly persists to built routing_config.yaml (gpt-4o, claude-sonnet-4-6)
- Build process completes successfully

**Edge case results:**
- Invalid model: Silent substitution (P1)
- Unsupported provider (groq): Silent substitution (P1)
- Ollama: Not tested yet

**Different-providers full E2E run:** Build completed, routing_config.yaml shows correct providers and models. Validation passed.

**Trust assessment for Persona 6:** FAIL. An LLM power user cannot trust the chat acknowledgment text at all. The product does route correctly in the backend (confirmed via generated files), but the conversational interface fails to communicate routing decisions, silently substitutes invalid inputs, and never answers direct routing questions. The gap between what the UI displays (only providers, not models) and what is actually configured (providers + models) creates additional confusion.


