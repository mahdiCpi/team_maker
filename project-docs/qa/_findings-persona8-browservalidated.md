# Persona 8 findings — Non-native / imprecise user (Browser Use validated)

Commit under test: b9460305bcc3f61dce51476816ac6bf8a9dc46a9 (branch story_4_8).
Servers: web :3000, API :8000.
Browser: Chrome via browser-harness (Browser Use - PRIMARY interaction mechanism).

## Persona 8 summary

**Scenarios to perform:**
1. Grammatical mistakes and incomplete descriptions
2. Ambiguous terminology  
3. Very short instructions
4. Follow-up corrections
5. Scenario partly in another language

**Methodology:** All scenarios performed using browser-harness with actual Chrome interaction (no API-only testing).

---

## P8-F1 — Positive: System correctly interprets imprecise input with grammatical mistakes

- **Persona:** 8 (Non-native/imprecise user). **Journey stage:** Compose.
- **Steps:**
  1. Sent: "make team for help plan week but not sure what role need" (grammatical mistakes, incomplete description)
  2. System generated team proposal
- **Expected:** System should attempt to interpret the imprecise request and propose a relevant team.
- **Actual:** System successfully proposed: `intake_agent → scheduler_agent → wellness_advisor → summary_writer` with all models set to anthropic (keys found).
- **Severity:** **Positive finding** — The system handles poor grammar and incomplete descriptions gracefully.
- **Evidence:** Screenshot: `p8_s1_imprecise_input_response.png`; raw page text captured via `document.body.innerText`.
- **Systemic:** No — this is a positive outlier, not a defect.

---

## P8-F2 — Positive: System adapts to ambiguous terminology in fresh session

- **Persona:** 8 (Non-native/imprecise user). **Journey stage:** Compose.
- **Steps:**
  1. Fresh browser session (page reload)
  2. Sent: "create a team to handle the data processing" (ambiguous terminology)
  3. System generated team proposal
- **Expected:** System should interpret ambiguous request and propose a relevant team.
- **Actual:** System successfully proposed: `data_ingestion_agent → data_validation_agent → data_transformation_agent → data_analysis_agent → data_output_agent` — a 5-agent data pipeline team, contextually appropriate for "data processing".
- **Severity:** **Positive finding** — The system correctly disambiguates vague terminology.
- **Evidence:** Raw page text captured via `document.body.innerText`.
- **Systemic:** No

---

## P8-F3 — Positive: System handles very short input gracefully

- **Persona:** 8 (Non-native/imprecise user). **Journey stage:** Compose.
- **Steps:**
  1. Fresh browser session (page reload)
  2. Sent: "marketing" (very short, single-word instruction)
  3. System generated team proposal
- **Expected:** System should attempt to interpret minimal input.
- **Actual:** System successfully proposed: `marketing_strategist → seo_specialist → content_creator → social_media_manager → data_analyst` — a complete 5-agent marketing team, perfectly appropriate for the single word "marketing".
- **Severity:** **Positive finding** — The system handles minimal input exceptionally well.
- **Evidence:** Raw page text captured via `document.body.innerText`.
- **Systemic:** No

---

## P8-F4 — P2: Acknowledgment template doesn't explicitly confirm what changed

- **Persona:** 8 (Non-native/imprecise user). **Journey stage:** Compose/refine.
- **Steps:**
  1. Original team: marketing_strategist → seo_specialist → content_creator → social_media_manager → data_analyst
  2. Sent follow-up: "remove data_analyst"
  3. System response: "Updated: marketing_strategist → seo_specialist → content_creator → social_media_manager. Anything you would change about social_media_manager, or is this ready to build?"
- **Expected:** Acknowledgment should explicitly confirm "Removed data_analyst" or similar.
- **Actual:** Acknowledgment uses fixed template showing new role order but doesn't explicitly state what was removed/added/changed. The UI correctly shows only 4 agents (data_analyst removed), but the text acknowledgment is formulaic.
- **Severity:** **P2** (Moderate) — Matches the confirmed cross-persona pattern from Part 4, item 1. Creates mild confusion about what actually changed.
- **Evidence:** Raw page text showing both original team line and updated acknowledgment line.
- **Systemic:** Yes — same pattern as Persona 1-6 findings about acknowledgment text.

---

## P8-F5 — Positive: System correctly interprets mixed-language input

- **Persona:** 8 (Non-native/imprecise user). **Journey stage:** Compose.
- **Steps:**
  1. Fresh browser session (page reload)
  2. Sent: "crear un equipo para escribir articulo in english and spanish" (mixed Spanish/English)
  3. System generated team proposal
- **Expected:** System should interpret the mixed-language request and propose a relevant team.
- **Actual:** System successfully proposed: `researcher → english_writer → spanish_writer → editor → seo_optimizer` — a 5-agent bilingual content creation team, perfectly appropriate for the request.
- **Severity:** **Positive finding** — The system handles mixed-language input exceptionally well.
- **Evidence:** Raw page text captured via `document.body.innerText`.
- **Systemic:** No

---
