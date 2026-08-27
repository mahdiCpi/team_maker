# Persona 4 findings — Student / researcher

Commit under test: b9460305bcc3f61dce51476816ac6bf8a9dc46a9 (branch story_4_8). Servers already running (web :3000, API :8000).

## Persona 4 summary

**Scenarios performed:**
1. Baseline reasoning-only team: "I need a team to help me outline and structure my thesis on renewable energy policy, organizing my existing notes into a coherent argument." → built `thesis_outliner` (notes_analyst → argument_architect → chapter_planner → literature_advisor → editor_reviewer, all anthropic). Spec-reviewed only (not run), per audit brief guidance for the baseline.
2. Main scenario — explicit live-web-research need: "I need a team that researches the latest 2026 developments in fusion energy policy from the web and summarizes them for my literature review." → proposed `web_researcher → policy_analyst → literature_summarizer`. Asked directly in chat: "Can this actually search the live internet, or does it only know what's in its training data?" before building.
3. Built the team (`fusion_policy_research_team`) and inspected `generation_report.md`, `docs/how_to_run.md`, `docs/model_routing.md`, `agents/web_researcher.yaml`, and `tools.py` in the generated package.
4. Actually ran it end-to-end with a real research goal and read the full transcript.
5. Optional naive/ambiguous live-lookup phrasing: first "can you look this up for me: what's trending on Twitter about AI right now" (not team-shaped), then a team-shaped rephrase ("I want a team that can look up what's trending on Twitter/X about AI right now and give me a summary.") → built `ai_twitter_trends` (twitter_scraper → data_analyst → summary_writer) as a second, independent reproduction of the core defect in a different domain.

**Successes:**
- Role proposals for all three domains (thesis outlining, web-research literature review, Twitter trend lookup) were sensible, on-domain, and appropriately scoped — no leaked jargon.
- The naive one-line lookup request ("can you look this up for me...") was correctly *not* treated as a team-build request — team_maker replied "Please describe the team you want to build and what they should do." instead of hallucinating an answer or fabricating a team from an ambiguous single sentence. This is a genuinely good piece of restraint.
- The baseline no-tool thesis team built cleanly with "Validation: Passed" and (aside from the systemic doc-template issues already logged by Personas 1-3, not re-logged here) nothing scenario-specific went wrong.
- The underlying CrewAI execution pipeline again ran to completion without crashing, and produced fluent, well-organized, professionally-formatted prose — consistent with Personas 2/3's finding that the core agent orchestration is solid; the trust gap is entirely in what surrounds it (validation, docs, disclosure).

**Failures — this session's headline result: the SERPER_API_KEY / web_search prediction is CONFIRMED, and the actual failure mode is worse than predicted:**
- P4-F1 (P0): The chat never answered the direct honesty question about live internet access — silently defaulted to the same generic template used for every other turn. See below.
- P4-F2 (P0, the primary finding): `generation_report.md` says "Validation: PASSED / No issues / No warnings" for a team whose only research-capable tool is a hard-coded stub that raises `NotImplementedError` if ever actually invoked, and whose docstring falsely tells the LLM agent that the tool "is NOT limited to training data and WILL surface 2026 content." No doc anywhere mentions this. The actual Run produced a booklength, heavily-"cited" literature review that the agent's own first-draft message honestly admitted was based on training-data knowledge (cutoff ~early 2025) — and that one honest disclaimer was silently dropped by the final downstream summarization stage, leaving the published deliverable with zero indication that no web search ever happened.
- P4-F3 (P1, systemic, reproduced 3x total across personas 1-4 now, not re-logged as new): `how_to_run.md` "No API keys required" recurs verbatim for both `fusion_policy_research_team` and `ai_twitter_trends`, despite all agents requiring `ANTHROPIC_API_KEY` — noting recurrence per audit brief instruction, not counted as a new finding.
- P4-F4 (P1, new but same class as F9/P4-F2): the *identical* broken-stub-tool pattern reproduces for a completely different, even more obviously "must be live" request (Twitter/X trending topics) — `twitter_search_tool` checks `TWITTER_BEARER_TOKEN`, is unconditionally a `raise NotImplementedError` stub, and is undisclosed anywhere in generation_report.md/docs.
- P4-F5 (P2, new, related): tools assigned in agent YAML that aren't part of the *conditionally-gated* set (e.g. `file_read`, `text_summarizer`, `file_reader`, `text_analysis`, `file_writer`) don't appear in `TOOL_REGISTRY` under those names *at all* — not gated by any env var, just permanently absent. This affects the plain-reasoning baseline team too, not only the web-research teams.

**Usability / trust observations:** A student/researcher persona is the worst-case audience for this defect: the entire point of the request was "get me current information I can cite in an academic literature review," and the product delivered a document formatted exactly like a citation-backed literature review (named sources, dated reports, specific dollar figures, a "Source Base: ... 47 Primary and Secondary Sources" line) with a green "Complete" banner — while having never made a single real web request. A student relying on this for actual coursework could not tell, from the UI or the shipped docs, that these citations are unverified LLM output rather than the product of the live search the team was explicitly built and asked to perform. The one moment of honesty (the web_researcher stage's own knowledge-cutoff disclosure) was silently edited out by the next pipeline stage before reaching the user-facing deliverable — this is a new, worse variant of the "silent healing hides defects" pattern Persona 3 found for truncation (P3-F2): here it hides an active capability-gap admission, not just a formatting glitch.

---

## P4-F1 — Direct honesty question about live web access ("Can this actually search the live internet, or does it only know what's in its training data?") gets zero answer, same generic template as every other turn

- Persona: 4 (student/researcher). Journey stage: Compose/refine, immediately before Build.
- Team: `fusion_policy_research_team` (web_researcher → policy_analyst → literature_summarizer).
- Steps: after team_maker proposed the 3-role team for "researches the latest 2026 developments in fusion energy policy from the web," sent verbatim: "Can this actually search the live internet, or does it only know what's in its training data?"
- Expected: An honest, direct answer — ideally disclosing that `web_search` requires a `SERPER_API_KEY` that is not configured on this machine, so the team as currently built cannot do live web research.
- Actual: `team_maker`'s reply was: "Updated: web_researcher → policy_analyst → literature_summarizer. Anything you would change about literature_summarizer, or is this ready to build?" — byte-identical in structure to every other turn's boilerplate. No answer to the question was given at all; the conversation proceeded as if the user had asked for a routine edit.
- This extends the already-logged pattern (Persona 1 F1/F2, Persona 2 P2-F3, Persona 3's recurrence note) with the single most damaging instance of it found in the whole audit: this is precisely the question a careful user would ask specifically to protect themselves from the defect this audit is investigating, and the product's answer-suppression mechanism suppressed it exactly the same as any other unanswered question.
- Severity: **P0** — the question was asked in the exact scenario where an honest answer would have prevented the user from being misled about a capability gap that materially affects deliverable accuracy (a false-negative "capability check" that a diligent user did everything right to ask, and got nothing).
- Evidence: raw chat transcript in this session (`document.body.innerText`, quoted above); reproduced pattern from Persona 1 F1/F2, Persona 2 P2-F3.

## P4-F2 — CONFIRMED: `web_search` (and its sibling stub tools) is validated "Passed" with zero disclosure, and the actual generated stub is worse than predicted — it raises `NotImplementedError` if invoked, its own docstring falsely claims live-web capability, and the run's one honest self-disclosure was silently dropped before reaching the final deliverable

- Persona: 4. Journey stage: Build → generated package → Run → Transcript. Team: `fusion_policy_research_team`.
- **Step 1 — spec/build.** `agents/web_researcher.yaml`:
  ```yaml
  tools:
  - web_search
  - web_scraper
  - url_reader
  ```
- **Step 2 — generation_report.md** (quoted in full, no secrets):
  ```
  **Validation status:** ✅ PASSED
  ...
  ## Validation
  ### Issues
  _No issues found._
  ### Warnings
  _No warnings._
  ```
  Zero mention of `web_search`, `SERPER_API_KEY`, or any tool-availability caveat anywhere in the report.
- **Step 3 — `docs/how_to_run.md`** "## Environment Variables" section: `_No API keys required (local models only)._` — same false claim already flagged by Personas 1-3 for other teams, reproduced here for the team whose entire purpose is live web research.
- **Step 4 — `docs/model_routing.md`**: describes only LLM provider routing (`anthropic`/`openai`/`ollama` etc.); zero mention of tool credentials anywhere in the file.
- **Step 5 — `tools.py` (the actual generated, executable code)** — this is where the real mechanism turned out to differ from (and be worse than) the pre-browser prediction:
  ```python
  @tool("web_search")
  def web_search_tool(input: str) -> str:
      """Performs live internet searches using a search API (e.g. SerpAPI, Tavily, or Brave Search) to
      retrieve real-time web results. Requires a valid API key set in the environment. This tool
      fetches current information from the live web — it is NOT limited to training data and WILL
      surface 2026 content as it is published online."""
      serpapi_api_key = os.environ.get("SERPAPI_API_KEY", "")
      if not serpapi_api_key:
          return "[error] SERPAPI_API_KEY not set"
      # TODO: implement web_search
      raise NotImplementedError("Stub for 'web_search' — fill in tools.py")
  ```
  and further down:
  ```python
  TOOL_REGISTRY: dict[str, Any] = {
      ...
      "web_search": web_search_tool,   # <- the stub above, registered unconditionally
      "url_reader": url_reader_tool,   # <- also an unconditional NotImplementedError stub
      "web_scraper": web_scraper_tool, # <- also an unconditional NotImplementedError stub
  }
  if _crewai_tools:
      ...
      if os.environ.get("SERPER_API_KEY"):          # <- different env var name than the stub checks!
          TOOL_REGISTRY["web_search"] = SerperDevTool()
      else:
          print("[warn] SERPER_API_KEY not set — web_search unavailable.")
  ```
  Because `SERPER_API_KEY` is absent on this machine, the conditional overwrite never fires, so `TOOL_REGISTRY["web_search"]` remains the hand-written stub — which itself checks a *different*, equally-unset env var (`SERPAPI_API_KEY`, not `SERPER_API_KEY`) and would `raise NotImplementedError` even if that env var were set. `url_reader` and `web_scraper` have no conditional path at all — they are permanently `NotImplementedError` stubs regardless of any key. This refines the audit brief's prediction: the failure mode is not "the tool silently disappears from the registry with a server-stdout warning" (that only applies to the small fixed set of tools the base template explicitly gates, i.e. `code_reader`/`web_search`-via-Serper) — for any *suggested/custom* tool name (which is what `web_search`/`web_scraper`/`url_reader` actually are here, since they're rendered via the `{% for t in suggested_tools %}` loop), the tool is *always* registered, but as a broken stub that would throw an unhandled exception if the agent ever actually called it.
- **Step 6 — actual Run.** Goal given: "Find the latest 2026 developments in fusion energy policy from the web (news, government announcements, regulatory changes) and summarize them for my literature review, citing sources." All 4 tasks reported **"Done"**; run banner showed **"Complete" / "Run complete."** with no warning of any kind.
  - Searched the full 174,906-character transcript (`project-docs/qa/evidence/p4_transcript_fusion_policy_research_team.txt`) for any trace of a tool invocation, tool error, or the strings `NotImplementedError`/`Action:`/`Tool:` — **zero matches**. The agent never attempted to call `web_search` at all (it simply produced text directly), so the `NotImplementedError` stub bug never actually triggered in this run — but it would have hard-failed the tool call if the LLM ever had chosen to invoke it, which is itself a latent crash risk the validator/report gives no warning about either.
  - The `web_researcher` stage's own raw output (transcript lines 175 and 499) contains a genuinely honest admission the product never surfaces anywhere in the UI: *"This report compiles the latest available information on fusion energy policy developments as of 2025-2026... Note: As my knowledge extends through early 2025, I have compiled the most current available information and clearly noted where 2026 projections and anticipated developments are documented in policy roadmaps."* — i.e., the agent itself is telling us, unprompted, that it did not do live research and is working from training-data knowledge.
  - The final, user-facing deliverable (the `literature_summarizer` stage's output, transcript lines 1723+, and what's shown as the primary panel content) **drops that admission entirely**. It opens instead with: *"Prepared for Academic Literature Review... Source Base: Comprehensive Policy Analysis Drawing on 47 Primary and Secondary Sources (~85,000 words)"* and a vague *"A note on sources and scope: This review draws principally on policy documents, government reports, regulatory filings, and analyses from the 2022–2026 period. Where specific 2026 policy documents are not yet publicly available, the review relies on documented roadmaps..."* — hedged academic-sounding language that never actually states "no live web search occurred" or "this is not grounded in real citations." The output includes specific, invented-sounding citations (`NRC SECY-23-0063`, dollar figures, named companies, dated "Source:" URLs) formatted exactly like verified research.
- Why this matters: this is the single clearest possible demonstration of the audit brief's #1 concern — "does the product confidently claim a capability/result that fundamentally does not exist." Every layer that could have caught or disclosed this (chat honesty-question, generation_report validation, how_to_run.md, model_routing.md, the run's own success banner, and even the one internal moment of LLM self-honesty) either said nothing or was actively overwritten before reaching the user.
- Severity: **P0 — CONFIRMED** (source-level, network/file-level, and full end-to-end browser/transcript verified). Not merely PLAUSIBLE any longer.
- Evidence: `generated_teams/fusion_policy_research_team/agents/web_researcher.yaml`, `generation_report.md`, `docs/how_to_run.md`, `docs/model_routing.md`, `tools.py` (lines ~228-294, quoted above), `project-docs/qa/evidence/p4_transcript_fusion_policy_research_team.txt` (174,906 chars; disclosure at lines 175/499, final deliverable at lines 1723+).

## P4-F3 — Reproduced a second time in an unrelated domain: the same broken-stub-tool pattern for a Twitter/X "must be live" request, still undisclosed

- Persona: 4. Journey stage: Build / generated package. Team: `ai_twitter_trends` (twitter_scraper → data_analyst → summary_writer), built from "I want a team that can look up what's trending on Twitter/X about AI right now and give me a summary."
- `agents/twitter_scraper.yaml` → `tools: [twitter_search_tool, web_search_tool]`.
- `tools.py`:
  ```python
  @tool("twitter_search_tool")
  def twitter_search_tool_tool(input: str) -> str:
      """Searches Twitter/X for tweets, hashtags, and trending topics matching a given query. ...
      Requires a Twitter/X API bearer token."""
      twitter_bearer_token = os.environ.get("TWITTER_BEARER_TOKEN", "")
      if not twitter_bearer_token:
          return "[error] TWITTER_BEARER_TOKEN not set"
      # TODO: implement twitter_search_tool
      raise NotImplementedError("Stub for 'twitter_search_tool' — fill in tools.py")
  ```
  Registered unconditionally in `TOOL_REGISTRY`, identical pattern to P4-F2's `web_search`/`web_scraper`/`url_reader`.
- `generation_report.md`: "Validation status: ✅ PASSED", "No issues found.", "No warnings." — `TWITTER_BEARER_TOKEN` appears nowhere. `docs/how_to_run.md` again states "_No API keys required (local models only)._"
- Not run to completion (time-boxed), but the build-time evidence alone is sufficient: this is the identical defect class, independently confirmed in a second, very different domain that is if anything an even more obvious "this must be live data" request than the fusion-policy scenario.
- Severity: **P0** (same class as P4-F2, second independent reproduction as requested by the audit brief's "reproduce significant findings twice" guidance).
- Evidence: `generated_teams/ai_twitter_trends/agents/twitter_scraper.yaml`, `generation_report.md`, `docs/how_to_run.md`, `tools.py` (lines 228-241, 257-258).

## P4-F4 (new) — Tools with no explicit env-var gate at all are silently absent from TOOL_REGISTRY under their assigned names, even for a plain-reasoning team with no live-data need

- Persona: 4. Journey stage: Build / generated package. Team: `thesis_outliner` (baseline, no explicit tool request from the user).
- `agents/notes_analyst.yaml` was assigned `tools: [file_read, text_summarizer]` unprompted (the user never asked for file-reading capability; team_maker added it on its own for a "review my notes" role). Checked the generated `tools.py` for this team: neither `file_read` nor `text_summarizer` appears anywhere in `TOOL_REGISTRY` (the registry only exposes a `filesystem` key, mapped to a *list* of `[FileReadTool(), FileWriterTool()]` — a different name than what the agent YAML actually specifies).
- Same gap reproduced in `fusion_policy_research_team`'s `policy_analyst.yaml` (`tools: [file_reader, text_analysis]`) and `literature_summarizer.yaml` (`tools: [file_writer]`) — none of these three names appear in `TOOL_REGISTRY` either.
- At runtime, `get_tools_for()` will call `print(f"[warn] tool '{name}' not in registry — skipping.")` for every one of these — invisible to the web UI — and the agent will simply run with zero tools, not the file-reading/summarization capability its own YAML advertises.
- Why this matters: this shows the tool-availability gap is broader than just the SERPER_API_KEY-style conditionally-gated tools (`web_search`, `code_reader`). Any tool name team_maker's LLM invents that doesn't happen to match one of the ~9 hardcoded registry keys is unconditionally unavailable, with the same total silence in validation, docs, and UI as the gated case — this affects even a plain-reasoning, no-explicit-tool-request baseline team.
- Severity: **P1** (extends F9's scope; not independently P0 since these are lower-stakes "convenience" tools rather than the core deliverable-defining capability the user explicitly asked for, but it's the same undetected/undisclosed mechanism at a wider scale).
- Evidence: `generated_teams/thesis_outliner/agents/notes_analyst.yaml`, `generated_teams/fusion_policy_research_team/agents/policy_analyst.yaml` + `agents/literature_summarizer.yaml`, both teams' `tools.py` (`TOOL_REGISTRY` dict, `get_tools_for` function).

## P4-F5 (positive, with major caveat) — The naive one-line "look this up for me" phrasing was correctly not treated as a team-build request

- Persona: 4. Journey stage: Compose (very first turn).
- Sent, as the opening message of a brand-new conversation: "can you look this up for me: what's trending on Twitter about AI right now" — deliberately phrased as a direct question/request rather than "build me a team that...".
- team_maker's reply: "Please describe the team you want to build and what they should do." — it did not attempt to answer the question itself (good: no risk of a bare hallucinated answer presented as fact) and did not silently construct a team from an ambiguous one-liner.
- Caveat: this is a narrow win. The moment the *same underlying need* was rephrased even slightly toward "I want a team that can look up..." (P4-F3), the product proceeded straight into building a team with non-functional live-data tools and zero disclosure, per P4-F3 above. So this good behavior is about detecting whether the message is team-shaped at all, not about detecting or disclosing the live-data capability gap — it does not meaningfully mitigate P4-F1/F2/F3.
- Severity: N/A (positive finding, included for balance).
- Evidence: chat transcript captured this session (quoted above).

---

## Environment / setup facts (this session)

- Commit under test: `b9460305bcc3f61dce51476816ac6bf8a9dc46a9` (branch `story_4_8`), matching Personas 1-3's sessions.
- Confirmed via file/env grep before touching the browser: `SERPER_API_KEY` is absent from `team_maker.keys`, from the shell environment, and from `/api/keys/status` (which only tracks LLM provider keys — confirmed identical to the audit brief's stated setup).
- Three teams built this session: `thesis_outliner` (baseline, not run), `fusion_policy_research_team` (built and run to full completion — see P4-F2), `ai_twitter_trends` (built, not run — build-time evidence only, see P4-F3).
- `fill_input()` again reliably no-op'd on both the compose and run-goal textareas in this session (consistent with Personas 2/3's notes); worked around every time via a direct JS native-setter + `dispatchEvent(new Event('input', {bubbles:true}))` call rather than `type_text()`.
- Did not repeat the "My Teams" / navigation-reload-during-run checks or the general chat-boilerplate documentation in depth — already thoroughly confirmed broken/uninformative by Personas 1-3; P4-F1 is logged only because it is the specific, novel instance of asking the exact capability-honesty question this audit's primary mission depended on.
- Evidence files: `project-docs/qa/evidence/p4_transcript_fusion_policy_research_team.txt` (174,906 chars, full "View transcript" `document.body.innerText` capture).
