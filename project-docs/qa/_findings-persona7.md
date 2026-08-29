# Persona 7 findings — Software engineer (Browser Use validated)

Commit under test: b9460305bcc3f61dce51476816ac6bf8a9dc46a9 (branch story_4_8).
Servers: web :3000, API :8000.
Browser: Chrome via browser-harness (Browser Use - PRIMARY interaction mechanism).

## Persona 7 summary

**Scenarios to perform:**
1. Coding/review/testing team with explicit tool requirements (code reading, file writing, shell commands)
2. GitHub automation team with git_account tool
3. DevOps team with shell_command, test_runner, docker_runner tools
4. Full E2E run for software team
5. Verify tool availability at runtime

**Scenarios completed:** 5/5 (all completed)

**Methodology:** All scenarios performed using browser-harness with actual Chrome interaction (no API-only testing).

---

## P7-F1 — P0: Generated agent YAMLs reference tool stubs that raise NotImplementedError

- **Persona:** 7 (Software engineer). **Journey stage:** Build / generated files.
- **Steps:**
  1. Requested: "Create a team for code review and testing: one agent reads and reviews code, one writes unit tests, one runs the tests. They need code reading, file writing, and shell command capabilities."
  2. Team created: code_reviewer → test_writer → test_runner (all anthropic/claude-sonnet-4-6)
  3. Clicked Build
  4. Generated team: `generated_teams/code_review_and_testing/`
  5. Read agent YAML files and tools.py
- **Expected:** Agent YAML tool names should match implementable tools in tools.py that can actually perform the requested operations.
- **Actual:** 
  - `agents/code_reviewer.yaml`: tools: [code_reader_tool, file_writer_tool]
  - `agents/test_writer.yaml`: tools: [code_reader_tool, file_writer_tool]
  - `agents/test_runner.yaml`: tools: [shell_tool, file_writer_tool]
  - `tools.py` contains these tools as **NotImplementedError stubs**:
    ```python
    @tool("code_reader_tool")
    def code_reader_tool_tool(input: str) -> str:
        raise NotImplementedError("Stub for 'code_reader_tool' — fill in tools.py")
    @tool("file_writer_tool")
    def file_writer_tool_tool(input: str) -> str:
        raise NotImplementedError("Stub for 'file_writer_tool' — fill in tools.py")
    @tool("shell_tool")
    def shell_tool_tool(input: str) -> str:
        raise NotImplementedError("Stub for 'shell_tool' — fill in tools.py")
    ```
  - Meanwhile, tools.py DOES contain real implementations: shell_command, code_writer, http_client, test_runner, docker_runner, git_account, state_reader, state_writer, ci_tool
  - **Tool naming mismatch:** Agents reference code_reader_tool/shell_tool/file_writer_tool (stubs) instead of code_reader/shell_command/code_writer (real tools)
  - **Validation PASSED anyway:** generation_report.md shows "✅ PASSED / No issues found / No warnings"
- **Severity:** **P0** (Release blocker) — Confidently false capability. The product claims the team can perform code reading, file writing, and shell commands, but the tools referenced will throw NotImplementedError at runtime. This is exactly the tool/capability hallucination defect class from audit brief section 5.
- **Evidence:** 
  - `generated_teams/code_review_and_testing/agents/*.yaml` (tool references)
  - `generated_teams/code_review_and_testing/tools.py` (stub implementations)
  - `generated_teams/code_review_and_testing/generation_report.md` (false validation pass)
- **Systemic:** Yes — confirmed pattern from Persona 4. The validator only checks file existence, never tool implementation quality or registry availability.

---

## P7-F2 — P0: GitHub team references git_account_tool stub instead of real git_account implementation

- **Persona:** 7 (Software engineer). **Journey stage:** Build / generated files.
- **Steps:**
  1. Requested: "Create a GitHub PR automation team with unique name. Needs git_account tool."
  2. Team created: github_automation_agent → anthropic
  3. Clicked Build
  4. Generated team: `generated_teams/github_automation_team/` (note: name normalized from github_automation_agent to github_automation_team)
  5. Read agent YAML and tools.py
- **Expected:** Agent should reference git_account (the real implementation that uses GITHUB_TOKEN).
- **Actual:** 
  - `agents/github_automation_agent.yaml`: tools: [git_account_tool, shell_tool, file_read_tool, file_write_tool]
  - `tools.py` contains:
    - `git_account` (real implementation with GITHUB_TOKEN check)
    - `git_account_tool` (stub that raises NotImplementedError)
    - `shell_tool` (stub), `file_read_tool` (stub), `file_write_tool` (stub)
  - **Tool naming mismatch:** Agent references git_account_tool (stub) instead of git_account (real)
  - **Validation PASSED:** generation_report.md shows "✅ PASSED / No issues found"
- **Severity:** **P0** (Release blocker) — Confidently false capability. The product claims the team can use GitHub API via git_account_tool, but that tool is a stub that will throw NotImplementedError. The real git_account implementation exists in the same file but is not referenced by the agent.
- **Evidence:** 
  - `generated_teams/github_automation_team/agents/github_automation_agent.yaml` (references git_account_tool stub)
  - `generated_teams/github_automation_team/tools.py` (contains both real git_account and stub git_account_tool)
  - `generated_teams/github_automation_team/generation_report.md` (false validation pass)
- **Systemic:** Yes — same tool naming mismatch pattern as P7-F1. This is a confirmed cross-scenario issue.

---

## P7-F3 — P2: Team name normalization not disclosed to user, causes confusing directory conflicts

- **Persona:** 7 (Software engineer). **Journey stage:** Build.
- **Steps:**
  1. Created team named "github_automation_agent"
  2. Attempted to Build, got error: "A directory already exists where this team would be written"
  3. Dismissed error, created different team with name "GitHub PR automation team with unique name"
  4. UI showed agent as "github_automation_agent"
  5. Clicked Build, succeeded
  6. Generated directory is `generated_teams/github_automation_team/` (not github_automation_agent)
- **Expected:** System should either: (a) accept the team name as-is, or (b) clearly disclose what the normalized name will be before Build.
- **Actual:** 
  - Team names are silently normalized (spaces, hyphens, etc. converted to underscores)
  - User sees "github_automation_agent" in UI but directory is "github_automation_team"
  - First Build attempt failed with confusing error about existing directory
  - No indication of what normalization rules are applied
- **Severity:** **P2** (Moderate) — Significant confusion. User cannot predict what directory name will be used, leading to "already exists" errors and manual cleanup.
- **Evidence:** Browser Use interaction captured. Directory created as github_automation_team despite UI showing github_automation_agent.
- **Systemic:** Yes — naming normalization logic not transparent to users.

---

## P7-F4 — P0: Suggested tools generate stubs that override built-in implementations (duplicate TOOL_REGISTRY keys)

- **Persona:** 7 (Software engineer). **Journey stage:** Build / generated files.
- **Steps:**
  1. Requested: "Create a DevOps team: one agent manages CI/CD, one runs tests, one deploys. Use shell_command, test_runner, and docker_runner tools explicitly."
  2. Team created: cicd_manager → test_runner_agent → deployment_agent
  3. Clicked Build
  4. Generated team: `generated_teams/devops_team/`
  5. Read agent YAMLs and tools.py
- **Expected:** Agent tools (shell_command, test_runner, docker_runner) should map to the real implementations in tools.py.
- **Actual:** 
  - Agent YAMLs correctly reference: shell_command, test_runner, docker_runner
  - tools.py contains BOTH real implementations AND stubs:
    - Real: `shell_command_tool(command: str)` → calls `_run_sandboxed`
    - Stub: `shell_command_tool(input: str)` → raises NotImplementedError
    - Both decorated with `@tool("shell_command")`
  - TOOL_REGISTRY has **duplicate keys** causing stubs to overwrite real implementations:
    ```python
    TOOL_REGISTRY: dict[str, Any] = {
        "test_runner":  test_runner_tool,  # first (real?)
        "docker_runner": docker_runner_tool, # first (real?)
        ...
        "test_runner": test_runner_tool,   # second (stub) - OVERWRITES first
        "docker_runner": docker_runner_tool, # second (stub) - OVERWRITES first
        "shell_command": shell_command_tool,  # stub only
    }
    ```
  - Since Python dict keys must be unique, the **stubs win** and overwrite the real implementations
  - Validation PASSED: generation_report.md shows "✅ PASSED / No issues found"
- **Severity:** **P0** (Release blocker) — Confidently false capability. Even when agents reference the correct tool names (shell_command, test_runner, docker_runner), the TOOL_REGISTRY contains duplicate keys that cause stubs to override real implementations. This is the **suggested tools stub override** issue from the API-based findings.
- **Evidence:** 
  - `generated_teams/devops_team/agents/*.yaml` (correct tool references)
  - `generated_teams/devops_team/tools.py` (duplicate tool definitions, stubs overwrite real)
  - `generated_teams/devops_team/generation_report.md` (false validation pass)
- **Systemic:** Yes — confirmed pattern. This is the same issue as P7-F9 from the original API-based findings.

---

## P7-F5 — P0: Agents fabricate detailed Docker/registry output when docker_runner is a NotImplementedError stub

- **Persona:** 7 (Software engineer). **Journey stage:** Run / Transcript.
- **Steps:**
  1. Built devops_team with agents: cicd_manager, test_runner_agent, deployment_agent
  2. All agents reference tools: shell_command, test_runner, docker_runner
  3. We confirmed (P7-F4) that these tools in TOOL_REGISTRY are mapped to NotImplementedError stubs
  4. Set goal: "Deploy the sample application to staging environment using CI/CD pipeline."
  5. Clicked Run
  6. Run completed after ~158 seconds with "Complete" status
  7. Clicked "View transcript"
- **Expected:** Either: (a) Run fails with NotImplementedError, or (b) error message about missing tools, or (c) honest disclosure that tools are not available.
- **Actual:** 
  - Run completed successfully with "Complete" / "Run complete" banners
  - Transcript shows **extremely detailed, plausible Docker operations**:
    - Registry authentication with timestamps: `[docker_runner] Login Succeeded — registry.example.com`
    - Multiple Docker layer pushes with specific SHA256 hashes: `sha256:1a2b3c4d...`, `sha256:5e6f7a8b...`, etc.
    - Versioned tags: `1.0.0-staging.a3f7d2e9`, `staging-latest`
    - Digest hashes: `sha256:d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5`
    - Duration timing: `47.2s`, `0.3s (layers cached)`
    - Layer-by-layer progress with sizes: `2.1MB / 2.1MB`, `39.8MB / 39.8MB`, etc.
  - **This is FABRICATED** - docker_runner is a NotImplementedError stub, so no actual Docker operations occurred
  - The UI reports "Complete" with no warnings
- **Severity:** **P0** (Release blocker) — Catastrophic trust failure. A software engineer would believe Docker images were actually built and pushed, when in fact no Docker operations occurred at all. The output is plausible enough to pass manual review.
- **Evidence:** 
  - Transcript at `/teams/devops_team` shows detailed Docker output
  - tools.py shows docker_runner_tool(input: str) raises NotImplementedError
  - TOOL_REGISTRY maps docker_runner to the stub
  - Run completed with no errors despite stub tool
- **Systemic:** Yes — this is the confirmed tool/capability hallucination pattern from Persona 4 (web_search stubs fabricating research). The agents fabricate plausible technical output when they cannot perform the actual operations.

---

## Persona 7 summary

**Top 5 findings:**
1. **P7-F5 (P0):** Agents fabricate detailed Docker/registry output when docker_runner is a NotImplementedError stub - catastrophic trust failure
2. **P7-F4 (P0):** Suggested tools generate stubs that override built-in implementations via duplicate TOOL_REGISTRY keys
3. **P7-F1 (P0):** Generated agent YAMLs reference tool stubs (code_reader_tool, file_writer_tool, shell_tool) that raise NotImplementedError
4. **P7-F2 (P0):** GitHub team references git_account_tool stub instead of real git_account implementation
5. **P7-F3 (P2):** Team name normalization not disclosed to user, causes confusing directory conflicts

**Positive findings:**
- Team composition with tool requirements works at the UI level
- Build process completes successfully (though tools may be stubs)
- Full E2E run completes with all agents reporting Done

**Tool/capability verification:**
- code_reader_tool/file_writer_tool/shell_tool: NotImplementedError stubs
- test_runner/docker_runner/git_account: Stub implementations override real implementations via duplicate registry keys
- git_account (real): Exists but not referenced by agents
- shell_command/code_writer/http_client: Real implementations exist but may be overridden

**Full E2E run for software team:** Completed with fabricated output. All agents reported Done despite using stub tools. Transcript shows detailed, plausible Docker operations that never actually occurred.

**Trust assessment for Persona 7:** **FAIL (Critical)**. A software engineer would be **completely misled** by this product. The agents produce **plausible, detailed, technical-looking output** (Docker layer pushes with SHA256 hashes, registry authentication, timing data) that appears genuine but is entirely fabricated. This is a **catastrophic trust failure**. The tool naming inconsistency means agents reference stubs instead of real implementations, yet they fabricate results anyway. The only positive is that the E2E workflow runs to completion, but the output cannot be trusted.


