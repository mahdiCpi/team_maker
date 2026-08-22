"""AC 7 (Story 4.5): `fields[].message` is always authored copy, never a raw
pydantic or composer message.

Covers `_authored_message` directly rather than only through a live request,
since the bug this regression-tests (pydantic's "Value error, " wrapper on
every custom validator message never being stripped, and the old fallback
mangling ordinary words via unscoped substring replacement) is about the
mapping function's own logic, not routing.
"""
from __future__ import annotations

from api.errors import (
    _GENERIC_FALLBACK_MESSAGE,
    _authored_message,
    fields_from_composer_errors,
    fields_from_error_list,
)


def test_custom_validator_value_error_prefix_is_stripped_and_authored():
    # Pydantic wraps every custom @field_validator ValueError in "Value error, ".
    raw = "Value error, Role name must be snake_case (lowercase letters, digits, underscores), got: 'BadName'"
    authored = _authored_message(raw)
    assert "Value error" not in authored
    assert "BadName" not in authored
    assert "snake_case" in authored.lower() or "lowercase" in authored.lower()


def test_task_and_tool_name_validators_are_also_authored():
    assert "lowercase" in _authored_message("Value error, Task name must be snake_case, got: 'Bad'").lower()
    assert "lowercase" in _authored_message("Value error, Tool name must be snake_case").lower()


def test_duplicate_role_names_is_authored():
    raw = "Value error, Duplicate role names in desired_roles: ['engineer']"
    authored = _authored_message(raw)
    assert "engineer" not in authored
    assert "unique" in authored.lower()


def test_pydantic_length_constraints_are_authored_with_interpolated_count():
    assert "3" in _authored_message("String should have at least 3 characters")
    assert "80" in _authored_message("String should have at most 80 characters")


def test_field_required_and_extra_forbidden_are_authored():
    assert _authored_message("Field required") != "Field required"
    assert _authored_message("Extra inputs are not permitted") != "Extra inputs are not permitted"


def test_unmatched_message_falls_back_to_fixed_generic_copy_not_a_transformation():
    # Regression: the old Tier 3 fallback did unscoped substring replacement
    # (`"str"` -> `"text"`, `"int"` -> `"number"`), which corrupted ordinary
    # words. Any message containing those substrings must not be mangled --
    # it must hit the fixed, content-free fallback instead.
    assert _authored_message("some constraint was violated") == _GENERIC_FALLBACK_MESSAGE
    assert _authored_message("a string with no known pattern") == _GENERIC_FALLBACK_MESSAGE
    assert "number" not in _authored_message("some constraint was violated")


def test_unmatched_message_never_leaks_the_raw_technical_text():
    secret_shaped = "unexpected token near sk-not-a-real-key-but-shaped-like-one"
    assert _authored_message(secret_shaped) == _GENERIC_FALLBACK_MESSAGE


def test_fields_from_composer_errors_uses_authored_copy():
    fields = fields_from_composer_errors(["desired_roles → 0 → name: Role name must be snake_case, got: 'Bad'"])
    assert len(fields) == 1
    assert "Bad" not in fields[0].message
    assert fields[0].path == "desired_roles.0.name"


def test_fields_from_error_list_uses_authored_copy():
    fields = fields_from_error_list([{"loc": ("team_name",), "msg": "Field required"}])
    assert len(fields) == 1
    assert fields[0].message != "Field required"
