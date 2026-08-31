"""Authorization policy tests (spec FR-050 to FR-055; Amendment 1; tasks
T049-T053, T082, T091)."""
from __future__ import annotations

from team_maker.tools.authorization import (
    AuthorizationPolicy,
    check_authorization,
    is_authorized,
)


class TestThreeNecessaryConditions:
    def test_declaration_alone_is_not_authorization(self):
        """FR-051: a team declaring docker_runner is not permission."""
        policy = AuthorizationPolicy()  # no tools enabled
        assert not is_authorized("docker_runner", {"docker_runner"}, policy)

    def test_risky_tool_denied_by_default(self):
        """FR-052: absence of enablement is denial, not permission."""
        policy = AuthorizationPolicy(enabled_tools=frozenset())
        for risky in ("shell", "code_writer", "test_runner", "docker_runner"):
            assert not is_authorized(risky, {risky}, policy)

    def test_risky_tool_authorized_when_explicitly_enabled(self):
        policy = AuthorizationPolicy(enabled_tools=frozenset({"docker_runner"}))
        assert is_authorized("docker_runner", {"docker_runner"}, policy)

    def test_safe_tool_authorized_without_any_enablement(self):
        """SAFE tools do not need operator enablement at all."""
        policy = AuthorizationPolicy()
        assert is_authorized("shell", set(), policy) is False  # not assigned -> condition 1 fails
        assert is_authorized("web_search", {"web_search"}, policy) is True

    def test_non_canonical_name_never_authorized(self):
        policy = AuthorizationPolicy(enabled_tools=frozenset({"text_summarizer"}))
        assert not is_authorized("text_summarizer", {"text_summarizer"}, policy)

    def test_not_assigned_to_team_is_not_authorized_even_if_enabled(self):
        policy = AuthorizationPolicy(enabled_tools=frozenset({"docker_runner"}))
        assert not is_authorized("docker_runner", set(), policy)


class TestUnreadablePolicyDenies:
    def test_empty_policy_denies_every_risky_tool(self):
        policy = AuthorizationPolicy()
        for risky in ("shell", "code_writer", "test_runner", "docker_runner"):
            assert not is_authorized(risky, {risky}, policy)


class TestCheckAuthorizationAggregation:
    def test_collects_every_unauthorized_risky_tool(self):
        """Collect-don't-short-circuit, matching preflight.check_credentials."""
        policy = AuthorizationPolicy()
        denied = check_authorization(["shell", "web_search", "docker_runner"], policy)
        assert set(denied) == {"shell", "docker_runner"}
        assert "web_search" not in denied  # SAFE, never denied

    def test_authorized_tools_excluded(self):
        policy = AuthorizationPolicy(enabled_tools=frozenset({"shell"}))
        denied = check_authorization(["shell", "docker_runner"], policy)
        assert denied == ["docker_runner"]
