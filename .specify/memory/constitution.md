<!--
Sync Impact Report
Version change: none (unfilled template placeholders) → 1.0.0
Bump rationale: Initial ratification. The prior file was the unfilled scaffold with
  no defined principles, so this is the first governing version, not an amendment.
Modified principles:
  [PRINCIPLE_1_NAME] → I. Compatibility Is Preserved By Default
  [PRINCIPLE_2_NAME] → II. Security Boundaries Fail Closed (NON-NEGOTIABLE)
  [PRINCIPLE_3_NAME] → III. Success Requires Execution Evidence
  [PRINCIPLE_4_NAME] → IV. Regression Fixes Start With A Failing Reproduction
  [PRINCIPLE_5_NAME] → V. Traceability And Test Gates
Added sections:
  [SECTION_2_NAME] → Security And Execution Constraints
  [SECTION_3_NAME] → Development Workflow And Quality Gates
Removed sections: none
Deferred items: none
-->

# TeamMaker Constitution

## Core Principles

### I. Compatibility Is Preserved By Default

A change MUST preserve, unless an approved spec explicitly changes it:

- Approved architecture decisions (AD-1 through AD-13 in the architecture spine).
- Public Python API surface and CLI surface — command names, options, argument
  semantics, exit codes, and output contracts.
- Provider-routing behavior, including per-agent routing and the conformance-gated
  runtime pin.
- Credential precedence: the key file wins; process environment variables are a
  fallback used only for providers the file does not set.
- Compatibility of previously generated Team Packages, which remain self-contained
  and independent of `team_maker` after generation.

Any deviation MUST cite the approved spec that authorizes it. "The spec did not
mention it" is not authorization to change it.

**Rationale:** Generated packages and downstream callers outlive the factory run that
produced them. Silent contract drift — especially in routing and credential
resolution — surfaces as a production failure far from the commit that caused it.

### II. Security Boundaries Fail Closed (NON-NEGOTIABLE)

A tool MUST execute only when all five conditions hold simultaneously:

1. **Canonical** — the tool resolves to a canonical identity in the tool catalog.
2. **Semantically valid** — its declaration and invocation pass semantic validation,
   not merely syntactic parsing.
3. **Resolvable** — its implementation is resolvable at execution time.
4. **Explicitly authorized** — authorization is granted explicitly; absence of a
   denial is not authorization.
5. **Sandboxed** — execution occurs inside the sandbox boundary.

If any condition is unmet, indeterminate, or unverifiable, execution MUST be refused.
No default-allow path, no permissive fallback, and no "best effort" degradation to an
unchecked execution route may exist.

**Rationale:** A gate that opens on uncertainty is not a gate. Fail-closed is the only
posture in which an unanticipated input path is safe by construction.

### III. Success Requires Execution Evidence

A run MUST NOT report successful completion without verifiable execution evidence.
Reported success MUST be derived from observed artifacts of the work actually
performed — transcripts, tool results, written artifacts, exit status — never from the
absence of an error, an unexercised code path, or an assumed outcome.

Where evidence is missing or cannot be verified, the run MUST report an indeterminate
or failed outcome. Mocked, stubbed, or simulated execution MUST be labeled as such and
MUST NOT be presented as evidence that a real integration works.

**Rationale:** A false success is more expensive than a failure, because it removes the
signal that would have prompted investigation.

### IV. Regression Fixes Start With A Failing Reproduction

Every regression fix MUST begin with a test that reproduces the defect and fails before
the fix is applied. The reproduction MUST be committed as part of the fix.

A behavioral finding MUST NOT be marked verified unless its original reproduction was
exercised against the changed code. Verification by inspection, by analogy to a similar
passing test, or by a newly written test that never demonstrated the failure does not
satisfy this requirement.

**Rationale:** A fix without a red-first reproduction proves only that some test passes.
Re-running the original reproduction is the sole evidence that the reported behavior —
and not an adjacent one — is gone.

### V. Traceability And Test Gates

Every change MUST trace to its originating requirement and to every applicable audit
finding ID (for example `RC-<n>`, `SECY-<n>`) in its commit message, story file, or
pull request description.

A change MUST NOT merge until unit tests, integration tests, security-regression tests,
and all end-to-end tests relevant to the touched surface pass. Security-regression
tests, once added, are permanent: they MUST NOT be deleted, skipped, or weakened to
accommodate a change.

**Rationale:** Untraced changes cannot be audited, and a finding whose regression test
has been disabled has been reopened, not closed.

## Security And Execution Constraints

- The tool catalog is the single source of tool identity. Execution paths that bypass
  catalog resolution are prohibited.
- Authorization decisions and refusals MUST be observable — a refused execution MUST
  produce a diagnostic naming the unmet condition from Principle II.
- Credentials are held as `SecretStr`, unwrapped only at the point of use, and MUST NOT
  appear in request YAML, generated packages, logs, transcripts, error messages, or
  test fixtures.
- Provider key names MUST match the provider catalog exactly; a mismatch is reported,
  never silently resolved to a different provider or key.
- Widening the runtime dependency pin requires the multi-provider conformance test to
  pass on the new version first (AD-7).

## Development Workflow And Quality Gates

- Branching follows the project rules in `CLAUDE.md`: `epic_<n>` per epic,
  `story_<epic>_<story>` branched from its epic, merged back on acceptance, and every
  branch created on the remote.
- Code and tests are organized by domain and responsibility, not accumulated flat. Test
  files MUST clearly identify mocks, stubs, fakes, monkeypatches, synthetic data,
  simulated services, and skipped tests.
- Test reports MUST distinguish unit, mocked integration, local integration,
  sandbox/testnet, and real end-to-end results.
- Review MUST verify: the compatibility surfaces in Principle I are intact, the
  five-condition gate in Principle II has no bypass, success reporting is
  evidence-backed, each regression fix carries its red-first reproduction, and
  traceability IDs are present.
- A finding may be closed only when its reproduction has been re-run against the merged
  code and its regression test is in the permanent suite.

## Governance

This constitution supersedes conflicting practices, conventions, and prior guidance for
TeamMaker. Where it conflicts with another document, this constitution governs until
amended.

**Amendment procedure.** Amendments require a written proposal stating the changed
text, the rationale, and the migration impact on in-flight work; explicit approval by
the project owner; and an update to this file in the same change that records the new
version and amendment date.

**Versioning policy.** This constitution uses semantic versioning. MAJOR for
backward-incompatible governance changes, principle removals, or redefinitions that
invalidate prior compliance. MINOR for a new principle or section, or materially
expanded guidance. PATCH for clarifications, wording, and non-semantic refinements.

**Compliance review.** Every pull request and review MUST verify compliance with the
Core Principles. Complexity and any deviation MUST be justified in writing against the
specific principle it strains, and an unjustified deviation blocks merge. Use
`CLAUDE.md` for runtime development guidance.

**Version**: 1.0.0 | **Ratified**: 2026-08-29 | **Last Amended**: 2026-08-29
