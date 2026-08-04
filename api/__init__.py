"""The HTTP seam (Story 2.0).

AD-4 admits no exception: `UI -> API -> core (ports) -> adapters`, and the UI
reaches the system *only* through here. This package is L2 — it translates HTTP
into calls on the Python core and never reimplements core behaviour. Nothing
under `team_maker/` may import from `api/`.

These routes are an internal precursor, not the public contract; Epic 4's
FR-16/FR-17 own the versioned public surface and may rename them.
"""
