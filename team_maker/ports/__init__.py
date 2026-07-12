"""Ports — the interfaces (Protocols) the core depends on.

Concrete implementations live under ``team_maker/adapters/`` and are wired in at
composition time. Per the architecture spine (AD-2/AD-4), core code imports only
from this package, never a concrete adapter.
"""
from __future__ import annotations
