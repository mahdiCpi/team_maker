"""Repo invariants for the dev topology (Story 2.0, AC 6).

These do not modify `web/` — they read it. The invariants they hold are the
kind that break silently: a `web/app/api/` directory added by a later story
would shadow the rewrite and every API call would start 404ing against Next
instead of reaching FastAPI, with no error anywhere to explain it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "web"
NEXT_CONFIG = WEB / "next.config.ts"


def test_no_filesystem_route_shadows_the_rewrite():
    assert not (WEB / "app" / "api").exists(), (
        "web/app/api/ would shadow the /api/:path* rewrite with a filesystem route"
    )


def test_the_rewrite_exists_and_is_environment_driven():
    config = NEXT_CONFIG.read_text(encoding="utf-8")

    assert "rewrites" in config
    assert "/api/:path*" in config
    assert "process.env.API_ORIGIN" in config
    assert "http://localhost:8000" in config
    # 3001 is `next dev`'s own fallback port, never the API's.
    assert ":3001" not in config


def test_no_cors_middleware_is_installed():
    """Same-origin by construction means CORS is not merely unused — its
    presence would mean someone reintroduced a cross-origin topology.

    Parsed rather than grepped: a plain text scan matches this repo's own
    prose about *not* using CORS, which would make the guard fire on its own
    documentation — a guard whose scope is wider than its claim.
    """
    import ast

    offenders: list[str] = []
    for path in (REPO_ROOT / "api").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and "cors" in (node.module or "").lower():
                offenders.append(f"{path.name}: import from {node.module}")
            elif isinstance(node, ast.Name) and node.id == "CORSMiddleware":
                offenders.append(f"{path.name}: uses CORSMiddleware")
            elif isinstance(node, ast.Attribute) and node.attr == "CORSMiddleware":
                offenders.append(f"{path.name}: uses CORSMiddleware")

    assert offenders == []


def test_responses_carry_no_cors_headers(make_client):
    """The behavioural half: even a request that looks cross-origin gets no
    `Access-Control-*` back, because nothing is configured to send it."""
    harness = make_client()

    responses = [
        harness.client.get("/api/health", headers={"Origin": "http://localhost:3000"}),
        harness.client.options(
            "/api/compose/sessions",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        ),
    ]

    for response in responses:
        leaked = [name for name in response.headers if name.lower().startswith("access-control-")]
        assert leaked == [], f"CORS headers appeared on {response.request.url.path}: {leaked}"


@pytest.mark.parametrize("target", ["api-dev", "api-serve"])
def test_the_makefile_exposes_the_api_targets(target):
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert f"\n{target}:" in makefile
    assert target in makefile.splitlines()[0]  # declared in .PHONY


def test_api_dev_does_not_combine_reload_with_workers():
    """uvicorn rejects `--reload` together with `--workers`."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    api_dev_line = next(
        line for line in makefile.splitlines() if "uvicorn api.main:app --reload" in line
    )

    assert "--workers" not in api_dev_line


def test_api_serve_pins_a_single_worker():
    """Compose sessions live in an in-process dict (AC 7); a second worker
    makes them vanish at random.

    Scoped to the `api-serve` recipe rather than grepping the whole file: the
    original assertion passed if `--workers 1` appeared anywhere at all,
    including inside a comment or a different target.
    """
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    recipe = next(
        line
        for line in makefile.splitlines()
        if line.startswith("\t") and "uvicorn api.main:app" in line and "--reload" not in line
    )

    assert "--workers 1" in recipe
