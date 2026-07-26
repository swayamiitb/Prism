"""
Context Brain — FastAPI application
===================================

The HTTP surface the frontend (and CLI/debug tools) talk to. Routes live in
``app/router.py``; this module owns app construction + the lifespan that warms
providers and the graph schema on startup.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("context_brain.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm providers + graph schema on startup; close on shutdown."""
    from context_brain.contexts import create_context_providers

    log.info("warming context providers…")
    create_context_providers()

    try:
        from context_brain.graph_schema import ensure_schema

        ensure_schema()
        log.info("graph schema ensured")
    except Exception as exc:
        log.warning("could not ensure graph schema at startup (is Neo4j up?): %s", exc)

    yield

    try:
        from context_brain.graph_schema import close_driver

        close_driver()
    except Exception as exc:  # pragma: no cover
        log.warning("error closing graph driver: %s", exc)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Context Brain",
        description="An AI that understands how a company works and turns it into executable skills.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.router import router

    app.include_router(router)
    return app


app = create_app()
