# Persona 9 findings — Security/privacy-conscious user (Browser Use validated)

Commit under test: b9460305bcc3f61dce51476816ac6bf8a9dc46a9 (branch story_4_8).
Servers: web :3000, API :8000.
Browser: Chrome via browser-harness (Browser Use - PRIMARY interaction mechanism).

## Persona 9 summary

**Scenarios to perform:**
1. Where do I put my API key?
2. Can I paste my API key here?
3. Why do you need this key?
4. What gets stored?
5. Test Settings UI and key management

**Methodology:** All scenarios performed using browser-harness with actual Chrome interaction (no API-only testing).

**Progress:** 3/5 scenarios complete (Scenarios 1, 2, and 3 done)

---

## P9-F1 — P2: Non-team questions get unhelpful generic response

- **Persona:** 9 (Security/privacy-conscious user). **Journey stage:** Compose.
- **Steps:**
  1. Fresh session, sent: "Where do I put my API key?"
  2. System response: "Please describe the team you want to build and what they should do."
  3. Follow-up: "Can I paste my API key here?"
  4. Same response: "Please describe the team you want to build and what they should do."
- **Expected:** System should recognize non-team questions and provide appropriate guidance (e.g., "For API key management, go to Settings").
- **Actual:** System repeatedly gives the same generic template response, not addressing the user's actual question.
- **Severity:** **P2** (Moderate) — Creates confusion for users with legitimate non-composition questions.
- **Evidence:** Raw page text showing both questions and identical responses.
- **Systemic:** Yes — likely the same issue that causes acknowledgment template problems.

---

## P9-F3 — P2: Non-team question about API key purpose gets generic response

- **Persona:** 9 (Security/privacy-conscious user). **Journey stage:** Compose.
- **Steps:**
  1. Fresh session, sent: "Why do you need this key?"
  2. System response: "Enter sends. ⌘/Ctrl+Enter is unavailable: describe your team first — there is nothing to build yet."
- **Expected:** System should recognize non-team questions about API key purpose and provide appropriate guidance (e.g., explain that API keys are needed to access AI providers, direct user to Settings page, or provide a clear explanation).
- **Actual:** System gives a generic template response about describing a team, not addressing the user's question about API key purpose.
- **Severity:** **P2** (Moderate) — Creates confusion for security-conscious users who want to understand the system's requirements before providing sensitive information.
- **Evidence:** Raw page text: System response "Enter sends. ⌘/Ctrl+Enter is unavailable: describe your team first — there is nothing to build yet." to the question "Why do you need this key?".
- **Systemic:** Yes — Same issue as P9-F1; the system's response template doesn't handle non-team questions appropriately.
- **Related:** P9-F1 (same root cause)

---

## P9-F2 — Positive: Settings page has clear security warnings

- **Persona:** 9 (Security/privacy-conscious user). **Journey stage:** Settings.
- **Steps:**
  1. Navigated to Settings page
  2. Observed page content
- **Expected:** Settings should provide clear guidance on API key management and security.
- **Actual:** Settings page shows:
  - Key Config Path clearly displayed
  - Provider Key Status for all providers
  - Security warning: "Keep your Key Config file out of version control. Never paste or share its contents in chat, tickets, or screenshots. If a key may have leaked, rotate it at the provider."
  - No input fields for entering keys in the UI (managed via file)
- **Severity:** **Positive finding** — Excellent security design and clear user guidance.
- **Evidence:** Raw page text from Settings page.
- **Systemic:** No

---
