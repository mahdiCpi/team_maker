"""The generated module docstring must state the policy actually applied
(spec FR-011; tasks T048, T092). Before this remediation it claimed risky
tools sandbox "when SANDBOX_ENABLED=true" and named `docker_runner` — the one
tool that never did."""
from __future__ import annotations

from team_maker.codegen import render_template
from team_maker.schema.request import SandboxConfig
from team_maker.tools.limits import DEFAULT_CONTROLS
from team_maker.tools.policy import EMPTY_ALLOWLIST


def _render(**overrides) -> str:
    kwargs = dict(
        sandbox=SandboxConfig(),
        suggested_tools=[],
        context_dir=None,
        effective_network="none",
        network_allowed=False,
        controls=DEFAULT_CONTROLS,
        mount_allowlist=EMPTY_ALLOWLIST.entries,
    )
    kwargs.update(overrides)
    return render_template("tools.py.j2", **kwargs)


def test_docstring_does_not_claim_a_conditional_opt_in_toggle():
    out = _render()
    docstring = out.split('"""', 2)[1]
    assert "SANDBOX_ENABLED=true" not in docstring
    assert "when SANDBOX_ENABLED" not in docstring


def test_docstring_states_sandboxing_is_mandatory():
    out = _render()
    docstring = out.split('"""', 2)[1]
    assert "mandatory" in docstring.lower()
    assert "docker_runner" in docstring  # included, not singled out as the exception


def test_docstring_reflects_the_refusal_on_breach_not_silent_truncation():
    out = _render()
    docstring = out.split('"""', 2)[1]
    assert "ToolPolicyRefusal" in docstring
    assert "silently-truncated" in docstring or "never falls back" in docstring or "refused" in docstring


def test_docstring_network_claim_matches_the_effective_setting():
    denied = _render(effective_network="none", network_allowed=False)
    assert "denied" in denied.split('"""', 2)[1]

    allowed = _render(effective_network="bridge", network_allowed=True)
    assert "permitted" in allowed.split('"""', 2)[1]
