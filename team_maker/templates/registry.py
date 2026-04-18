"""Simple registry mapping template_id strings to template classes.

Call ``register(template_id)`` as a class decorator to add a template.
Import all template modules in team_maker/templates/__init__.py so the
decorators fire before any lookup is attempted.
"""
from __future__ import annotations

from typing import Dict, Type

from team_maker.templates.base import BaseTeamTemplate

_REGISTRY: Dict[str, Type[BaseTeamTemplate]] = {}


def register(template_id: str):
    """Class decorator that adds the template to the global registry."""

    def decorator(cls: Type[BaseTeamTemplate]) -> Type[BaseTeamTemplate]:
        cls.template_id = template_id
        _REGISTRY[template_id] = cls
        return cls

    return decorator


def get_template(template_id: str) -> BaseTeamTemplate:
    """Return a fresh instance of the requested template."""
    if template_id not in _REGISTRY:
        available = sorted(_REGISTRY.keys())
        raise ValueError(
            f"Unknown template {template_id!r}. Available templates: {available}"
        )
    return _REGISTRY[template_id]()


def list_templates() -> Dict[str, str]:
    """Return {template_id: description} for all registered templates."""
    return {tid: cls.description for tid, cls in sorted(_REGISTRY.items())}
