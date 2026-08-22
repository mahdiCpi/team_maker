"""The FastAPI application — the L2 layer AD-4 requires (Story 2.0, AC 1).

Run it with `make api-dev` (reload, one worker) or `make api-serve`. The browser
never talks to this directly: `web/next.config.ts` proxies `/api/:path*` here,
so every request the browser makes is same-origin and no CORS middleware,
preflight or `Access-Control-*` configuration exists anywhere in this repo.
"""
from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.deps import ProviderFactory, bridge_credentials, default_provider_factory
from api.errors import (
    INTERNAL_ERROR,
    METHOD_NOT_ALLOWED,
    NOT_FOUND,
    REQUEST_REJECTED,
    SPEC_INVALID,
    ApiError,
    fields_from_error_list,
)
from team_maker.utils.text_sanitizer import log_exception_safely
from api.routers.compose import router as compose_router
from api.routers.keys import router as keys_router
from api.routers.run import router as run_router
from api.routers.starters import router as starters_router
from api.routers.teams import router as teams_router
from api.runs import RunRegistry
from api.schemas import HealthView
from api.sessions import SessionRegistry
from api.state import STATE_ATTR, AppState
from team_maker.keyconfig import KeyConfig
from team_maker.ports.execution_engine import ExecutionEngine

logger = logging.getLogger("api")

health_router = APIRouter(tags=["health"])


@health_router.get("/health", response_model=HealthView)
async def health() -> HealthView:
    """Liveness. Deliberately trivial: AC 3's proof is that this still answers
    while a multi-second blocking compose turn is in flight.

    `async def` on purpose, and it is the one handler here that should be. It
    performs no I/O, so it costs the event loop nothing — whereas as a `def` it
    needed a token from the same 40-slot anyio threadpool the blocking compose
    handlers occupy, which meant enough concurrent turns could queue the
    liveness probe behind exactly the work it exists to report on. The compose
    handlers stay `def`; that part of AC 3 is unchanged and still proven.
    """
    return HealthView()


def create_app(
    *,
    provider_factory: ProviderFactory | None = None,
    execution_engine: ExecutionEngine | None = None,
) -> FastAPI:
    """Build the application.

    `provider_factory` exists so tests can inject a fake `LLMProvider` and stay
    fully offline (AC 9). Production leaves it `None` and gets
    `create_provider`, so AD-8 holds — every LLM reaches the system through the
    one port's factory.

    `execution_engine` is Story 2.4's second injection seam, with the same
    rationale: production leaves it `None`, and `run_team_package` falls back
    to its own lazy `CrewAIExecutionEngine` default, so AD-6 holds. Tests
    inject a fake so `tests/api/` can exercise the run routes without a real
    crewai run and real spend.
    """
    factory = provider_factory or default_provider_factory()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _warn_on_multiple_workers()
        key_config = KeyConfig.from_file()
        for warning in key_config.load_warnings:
            logger.warning("key config: %s", warning)
        # Bridged ONCE, here, and held for the process lifetime. Doing this
        # per-request would race under AC 3's threadpool concurrency — see the
        # long note in `api/deps.py`.
        # A second, file-only load. Its *names* record what the file itself defined
        # at boot, which is what later lets a deleted key be told apart from one
        # that only ever came from the environment (see `api/routers/keys.py`).
        file_providers = tuple(KeyConfig.from_file(include_env=False).keys)
        bridged = bridge_credentials(key_config)
        logger.info(
            "authoring credentials available for: %s",
            ", ".join(bridged) if bridged else "(none)",
        )
        run_registry = RunRegistry()
        setattr(
            app.state,
            STATE_ATTR,
            AppState(
                key_config=key_config,
                registry=SessionRegistry(),
                provider_factory=factory,
                bridged_providers=tuple(bridged),
                run_registry=run_registry,
                execution_engine=execution_engine,
                file_providers=file_providers,
            ),
        )
        yield
        # Story 2.4: the first thing in this process that can outlive the app.
        # A run has no timeout, so joining without a bound would hang an
        # ordinary restart for as long as an LLM-driven run cares to take;
        # `shutdown()` gives it a short bounded wait, then logs and lets the
        # daemon thread be terminated with the process rather than blocking
        # forever. See `api/runs.py:RunRegistry.shutdown` for the full
        # rationale.
        run_registry.shutdown()

    app = FastAPI(
        title="team_maker API",
        version="0.1.0",
        summary=(
            "Internal precursor to the versioned public contract (Epic 4 owns "
            "FR-16/FR-17). Routes here may be renamed."
        ),
        lifespan=lifespan,
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(compose_router, prefix="/api")
    # The key-status group (Story 2.3). Read-only: AD-9 forbids the browser
    # touching keys, so the UI's four states come from here.
    app.include_router(keys_router, prefix="/api")
    # The starters group (Story 3-1): read-only listing of shipped starter teams
    app.include_router(starters_router, prefix="/api")
    # The run group (Story 2.4). `run_router` declares `/teams/{team_slug}`
    # first internally, because it genuinely collides with
    # `/{run_id}/transcript` — both are two segments under `/runs` — and
    # Starlette resolves by declaration order. (It does not collide with
    # `/{run_id}`, which is one segment; see the comment in `routers/run.py`.)
    app.include_router(run_router, prefix="/api")
    # The teams group (Story 2-5): save, browse, rename, delete teams
    app.include_router(teams_router, prefix="/api")
    _register_error_handlers(app)
    return app


# ---------------------------------------------------------------------------
# Error handling — AC 2's envelope is total, AC 8's containment is absolute
# ---------------------------------------------------------------------------


def _register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(RequestValidationError, _handle_request_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    # Defence in depth. Every authored route already catches broadly, so this
    # only fires for a fault outside them (a serializer bug, say). Without it a
    # client would get Starlette's plain-text body instead of the envelope.
    app.add_exception_handler(Exception, _handle_unexpected)


def _envelope(error: ApiError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content=error.envelope())


def _handle_api_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return _envelope(exc)


def _handle_request_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Replace FastAPI's `{"detail": [...]}` with the envelope.

    This is also the AC 10 rejection path for a request that tries to supply a
    key: the request models are `extra="forbid"`, so an `api_key` field is a
    422 rather than a silently ignored extra. `fields_from_error_list` reads
    only `loc` and `msg`, never `input` — which for an `extra_forbidden` error
    holds the rejected value, i.e. the key itself.
    """
    errors = exc.errors() if isinstance(exc, RequestValidationError) else []
    return _envelope(
        ApiError(
            SPEC_INVALID,
            "The request body is not valid.",
            fields=fields_from_error_list(errors, strip_prefix="body."),
        )
    )


_HTTP_STATUS_CODES = {404: NOT_FOUND, 405: METHOD_NOT_ALLOWED}
_HTTP_STATUS_MESSAGES = {
    404: "No such endpoint.",
    405: "That method is not allowed on this endpoint.",
}


def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    """Put the envelope on a Starlette `HTTPException` without rewriting it.

    The earlier version mapped anything that was not 404 or 405 to
    `internal_error` and then took the *code's* status — so a 400, 401, 403,
    413 or 429 raised by a dependency or middleware reached the client as a 500
    saying the server had broken. It also dropped `exc.headers`, which is where
    a 405's mandatory `Allow` lives. The envelope is a shape promise; it was
    never meant to be a status rewrite.
    """
    status = int(getattr(exc, "status_code", 500) or 500)
    code = _HTTP_STATUS_CODES.get(status)
    if code is None:
        code = INTERNAL_ERROR if status >= 500 else REQUEST_REJECTED
    message = _HTTP_STATUS_MESSAGES.get(status)
    if message is None:
        message = (
            "Something went wrong on the server. The error has been logged."
            if status >= 500
            else "The request could not be completed."
        )
    # Built directly rather than through `_envelope`, because `ApiError` derives
    # its status from its code and here the exception's own status is the truth.
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}},
        headers=getattr(exc, "headers", None),
    )


def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    # Use safe logging to prevent sensitive data from leaking
    # Per AD-9: keys and sensitive data must never be logged
    log_exception_safely(logger, f"unhandled error serving {request.url.path}", exc)
    return _envelope(
        ApiError(
            INTERNAL_ERROR,
            "Something went wrong on the server. The error has been logged.",
        )
    )


def _warn_on_multiple_workers() -> None:
    """Compose sessions AND run state live in an in-process dict (AC 7; Story 2.4 AC 4).

    A second worker gets its own empty registry, so half of all requests would
    answer `session_not_found` for a session — or, since Story 2.4,
    `run_not_found` for a run — that is very much alive in the other process.
    Worse for a run: the process-wide lock that serialises runs
    (`api/runs.py`) is also per-worker, so a second worker does not merely
    lose track of a run, it lets two runs execute concurrently and corrupt
    each other's transcripts (`deferred-work.md:102`). That is a silent,
    intermittent failure, so it gets a loud startup warning.
    """
    configured = os.environ.get("WEB_CONCURRENCY")
    if configured and configured.strip() != "1":
        logger.warning(
            "WEB_CONCURRENCY=%s but compose sessions and run state are held "
            "in-process: with more than one worker, sessions and runs will appear to "
            "vanish at random, and concurrent runs will corrupt each other's "
            "transcripts. Run a single worker (see `make api-serve`).",
            configured,
        )
    # `uvicorn --workers 4` and `gunicorn -w 4` set no environment variable at
    # all, so reading WEB_CONCURRENCY alone missed the most obvious way an
    # operator trips this — the exact command the README warns against went
    # unwarned. The command line is the other place the truth lives.
    argv_workers = _workers_from_argv()
    if argv_workers is not None and argv_workers != 1:
        logger.warning(
            "started with %d workers, but compose sessions and run state are held "
            "in-process: sessions and runs will appear to vanish at random, and "
            "concurrent runs will corrupt each other's transcripts. Run a single "
            "worker (see `make api-serve`).",
            argv_workers,
        )


def _workers_from_argv() -> int | None:
    """The worker count from `--workers N`, `--workers=N` or `-w N`, if given."""
    argv = sys.argv[1:]
    for index, token in enumerate(argv):
        value: str | None = None
        if token in ("--workers", "-w"):
            value = argv[index + 1] if index + 1 < len(argv) else None
        elif token.startswith("--workers="):
            value = token.split("=", 1)[1]
        if value is not None:
            try:
                return int(value)
            except ValueError:
                return None
    return None


# The ASGI entrypoint used by `uvicorn api.main:app`.
app = create_app()
