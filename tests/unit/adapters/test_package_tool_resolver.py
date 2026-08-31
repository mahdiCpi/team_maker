"""Pre-remediation package-shape detection (spec FR-084; closes CHK040;
tasks.md T082) and the `PackageToolResolver` adapter (spec FR-019 to FR-025;
audit RC-5, P0-1; contracts/tool-resolver-port.md; tasks T097-T104)."""
from __future__ import annotations

import pytest

from team_maker.adapters.tools.package_tool_resolver import (
    PackageToolResolver,
    PreRemediationPackageError,
    check_package_shape,
)
from team_maker.codegen import render_template
from team_maker.ports.tool_resolver import (
    ResolvedTool,
    ToolPolicyError,
    UnknownToolError,
    UnresolvableToolError,
)
from team_maker.schema.request import SandboxConfig
from team_maker.tools.limits import DEFAULT_CONTROLS
from team_maker.tools.policy import EMPTY_ALLOWLIST

# A minimal excerpt of the actual pre-remediation template shape (the
# SANDBOX_ENABLED opt-out toggle this remediation deletes at T058, and no
# ToolPolicyRefusal marker since that class did not exist before Phase 4).
_OLD_SHAPE_SOURCE = '''
USE_SANDBOX = os.environ.get("SANDBOX_ENABLED", "false").lower() == "true"

def shell_tool(command):
    if USE_SANDBOX:
        return _run_sandboxed(command)
    return subprocess.run(command, shell=True, capture_output=True)
'''


def _current_shape_source() -> str:
    return render_template(
        "tools.py.j2",
        sandbox=SandboxConfig(),
        suggested_tools=[],
        context_dir=None,
        effective_network="none",
        network_allowed=False,
        controls=DEFAULT_CONTROLS,
        mount_allowlist=EMPTY_ALLOWLIST.entries,
    )


def test_current_shape_is_accepted():
    check_package_shape(_current_shape_source(), package_name="ok_team")  # must not raise


def test_old_shape_with_sandbox_enabled_toggle_is_refused():
    with pytest.raises(PreRemediationPackageError, match="ok_team|pre-remediation"):
        check_package_shape(_OLD_SHAPE_SOURCE, package_name="ok_team")


def test_module_missing_tool_policy_refusal_marker_is_refused():
    with pytest.raises(PreRemediationPackageError):
        check_package_shape("def shell_tool(command):\n    return run(command)\n", package_name="stub_team")


def test_refusal_message_is_actionable_and_names_the_package():
    with pytest.raises(PreRemediationPackageError, match="stub_team"):
        check_package_shape("", package_name="stub_team")


# ---------------------------------------------------------------------------
# PackageToolResolver
# ---------------------------------------------------------------------------


def _write_minimal_package(package_dir, *, use_vector: bool = False) -> None:
    """A real on-disk `tools.py` + `state_store.py`, the same two files a
    built package ships, so the resolver's actual import path (not a
    faked one) is exercised."""
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "tools.py").write_text(_current_shape_source(), encoding="utf-8")
    (package_dir / "state_store.py").write_text(
        render_template("state_store.py.j2", use_vector=use_vector, use_file=True),
        encoding="utf-8",
    )


def test_no_package_fallback_resolves_a_canonical_name_to_an_inert_tool():
    resolver = PackageToolResolver(None)
    result = resolver.resolve("shell")
    assert isinstance(result, ResolvedTool)
    assert result.name == "shell"
    assert result.instance.name == "shell"


def test_no_package_fallback_instance_raises_if_actually_invoked():
    resolver = PackageToolResolver(None)
    instance = resolver.resolve("shell").instance
    with pytest.raises(ToolPolicyError, match="no package to execute against"):
        instance.func("echo hi")


def test_non_canonical_name_is_unknown_regardless_of_package():
    resolver = PackageToolResolver(None)
    with pytest.raises(UnknownToolError):
        resolver.resolve("text_summarizer")


def test_real_package_resolves_to_the_actual_registry_entry(tmp_path):
    package_dir = tmp_path / "a_team"
    _write_minimal_package(package_dir)
    resolver = PackageToolResolver(package_dir)

    result = resolver.resolve("shell")
    assert result.name == "shell"
    assert result.instance.name == "shell"
    # The real binding, not the no-package inert stand-in — distinguished by
    # docstring, since the inert fallback copies the catalog description
    # verbatim onto a wrapper function that never mentions the sandbox.
    assert "Docker sandbox" in (result.instance.func.__doc__ or "")


def test_canonical_tool_with_no_package_binding_is_unresolvable(tmp_path, monkeypatch):
    """A registry that is missing an otherwise-canonical, implemented name —
    simulating drift between the catalog and a package built by a different
    team_maker version."""
    package_dir = tmp_path / "b_team"
    _write_minimal_package(package_dir)
    resolver = PackageToolResolver(package_dir)
    registry = resolver._load_registry()
    del registry["shell"]

    with pytest.raises(UnresolvableToolError, match="shell"):
        resolver.resolve("shell")


def test_pre_remediation_package_is_refused_not_partially_loaded(tmp_path):
    package_dir = tmp_path / "old_team"
    package_dir.mkdir()
    (package_dir / "tools.py").write_text(_OLD_SHAPE_SOURCE, encoding="utf-8")
    resolver = PackageToolResolver(package_dir)

    with pytest.raises(PreRemediationPackageError):
        resolver.resolve("shell")


def test_resolve_all_collects_every_failure_before_raising():
    resolver = PackageToolResolver(None)
    with pytest.raises(UnresolvableToolError) as exc_info:
        resolver.resolve_all(["shell", "text_summarizer", "docker_runner", "also_bogus"])
    message = str(exc_info.value)
    assert "text_summarizer" in message
    assert "also_bogus" in message


def test_resolve_all_of_only_valid_names_returns_every_instance():
    resolver = PackageToolResolver(None)
    resolved = resolver.resolve_all(["shell", "state_reader"])
    assert {r.name for r in resolved} == {"shell", "state_reader"}


def test_resolving_a_package_does_not_write_a_pycache_into_it(tmp_path):
    """Found via a broken build-idempotency test: importing `tools.py` to
    resolve/validate a package must not leave a `__pycache__/` behind —
    that is a derived artifact the user never asked for, and `.pyc` files
    are not byte-stable between two builds of identical source (cache
    invalidation embeds a timestamp/hash), which silently broke
    idempotency checks that diff a package's files across two builds."""
    package_dir = tmp_path / "no_pycache_team"
    _write_minimal_package(package_dir)
    PackageToolResolver(package_dir).resolve("shell")

    assert not (package_dir / "__pycache__").exists()


def test_two_different_packages_resolved_in_one_process_do_not_cross_contaminate(tmp_path):
    """Both packages define a top-level `tools`/`state_store` module —
    `sys.modules` caches by that bare name, so resolving package B right
    after package A must not silently hand back package A's registry."""
    package_a = tmp_path / "team_a"
    package_b = tmp_path / "team_b"
    _write_minimal_package(package_a)
    _write_minimal_package(package_b)
    # Make package B's rendering distinguishable: a different sandbox image.
    (package_b / "tools.py").write_text(
        render_template(
            "tools.py.j2",
            sandbox=SandboxConfig(image="python:3.11-slim"),
            suggested_tools=[],
            context_dir=None,
            effective_network="none",
            network_allowed=False,
            controls=DEFAULT_CONTROLS,
            mount_allowlist=EMPTY_ALLOWLIST.entries,
        ),
        encoding="utf-8",
    )

    resolver_a = PackageToolResolver(package_a)
    resolver_b = PackageToolResolver(package_b)
    resolver_a.resolve("shell")
    resolver_b.resolve("shell")

    assert resolver_a._load_registry() is not resolver_b._load_registry()


def test_tool_resolution_never_touches_check_credentials_or_key_config(tmp_path):
    """Contract test obligation "Credential isolation" (spec FR-022): tool
    resolution must not call, alter, or duplicate
    `preflight.check_credentials`, and must not change provider-credential
    precedence. `key_config` is accepted (wiring-shape parity) but nothing
    in resolution reads it — proven here by passing an object that raises
    if anything on it is ever accessed."""

    class _ExplodingKeyConfig:
        def __getattr__(self, item):
            raise AssertionError(f"PackageToolResolver must never touch key_config.{item}")

    package_dir = tmp_path / "c_team"
    _write_minimal_package(package_dir)
    resolver = PackageToolResolver(package_dir, key_config=_ExplodingKeyConfig())

    result = resolver.resolve("shell")  # must not raise via _ExplodingKeyConfig
    assert result.name == "shell"


def test_conditionally_available_tool_missing_from_registry_is_omitted_with_a_warning(tmp_path):
    """FR-065's UNAVAILABLE_HERE (a missing optional dependency/credential,
    here: `crewai-tools` not installed) is distinct from NO_IMPLEMENTATION —
    `resolve_all` omits it with a warning rather than refusing the whole
    run. This dev/test environment never has `crewai-tools` installed (it
    is only ever a *generated package's* dependency, never team_maker's own
    — see pyproject.toml), so `code_reader` is reliably absent from every
    built package's registry here, making this reproducible without mocks."""
    package_dir = tmp_path / "d_team"
    _write_minimal_package(package_dir)
    resolver = PackageToolResolver(package_dir)

    with pytest.warns(UserWarning, match="code_reader"):
        resolved = resolver.resolve_all(["state_reader", "code_reader"])

    assert {r.name for r in resolved} == {"state_reader"}


def test_conditionally_available_tool_missing_still_refuses_alongside_a_genuine_failure(tmp_path):
    """The leniency is additive, not a general escape hatch: a real failure
    among the batch still refuses the whole run (FR-023)."""
    package_dir = tmp_path / "e_team"
    _write_minimal_package(package_dir)
    resolver = PackageToolResolver(package_dir)

    with pytest.raises(UnresolvableToolError, match="also_bogus"):
        resolver.resolve_all(["code_reader", "also_bogus"])
